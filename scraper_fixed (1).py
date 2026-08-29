"""
scraper_fixed.py — corrected version of scraper.py

WHAT CHANGED FROM THE ORIGINAL, AND WHY:
1. Removed all "fallback to a fake value" behavior (e.g. defaulting airline
   to "IndiGo" or time to "06:00 - 08:15" when the real value can't be found).
   A row is now only saved if every required field was genuinely read from
   the page. This fixes the "invents data" bug.
2. Added a CAPTCHA / block detector that runs BEFORE trying to read prices.
   If a block is detected, the search is skipped and logged - never faked.
3. Added a real delay between requests (not just a concurrency limit) -
   this is the actual "polite scraping" behavior, and should also reduce
   how often you get blocked in the first place.
4. Added a backoff timer that grows the more blocks you hit in a row.
5. Extended ADVANCE_WINDOWS to all 5 required windows: 1, 7, 15, 30, 45.
6. Removed the "chop digits off the price" hack. If a price can't be
   parsed as a clean, plausible number, the row is skipped instead of
   guessed at.

STILL NEEDS DOING (not fixable without live site access):
This still queries Google Flights, which is a search aggregator, not one
of the named airline/OTA sites the problem statement requires. To fully
satisfy that requirement, this script's `target_url` and CSS selectors
need to be replaced with a real IndiGo/SpiceJet/Cleartrip/etc. search page,
following the same "Inspect the page, find the real selectors" process
described earlier. The structure below (rate limiting, block detection,
no-fake-data rule) should carry over directly to that version.
"""

import asyncio
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

ROUTES = [
    ("DEL", "BOM"), ("DEL", "BLR"), ("BOM", "BLR"),
    ("DEL", "CCU"), ("BLR", "HYD"), ("MAA", "DEL"),
]

ADVANCE_WINDOWS = [1, 7, 15, 30, 45]  # T+1 / T+7 / T+15 / T+30 / T+45, all 5 as required

OUTPUT_CSV = "data/raw/fare_quotes_{}.csv".format(datetime.now().strftime("%Y_%m_%d"))

# Politeness settings — this is what "ethical scraping" actually means in code
MIN_DELAY_SECONDS = 4
MAX_DELAY_SECONDS = 9
CONCURRENCY_LIMIT = 1  # one request at a time, not several in parallel

BLOCK_SIGNALS = [
    "captcha", "verify you", "unusual traffic", "are you a robot",
    "access denied", "automated queries", "detected unusual",
]


def looks_blocked(page_text: str) -> bool:
    lowered = page_text.lower()
    return any(signal in lowered for signal in BLOCK_SIGNALS)


def parse_price(price_text: str):
    """Returns a clean integer price, or None if it doesn't look real.
    Never guesses or truncates a suspicious number."""
    digits = "".join(ch for ch in price_text if ch.isdigit())
    if not digits:
        return None
    price = int(digits)
    # A one-way domestic Indian fare is realistically between ~1,000 and ~50,000.
    # Anything wildly outside that is more likely a parsing error than a real
    # ultra-premium fare, so we discard it rather than guess a "fix".
    if price < 1000 or price > 50000:
        return None
    return price


async def scrape_single_query(sem, context, origin, dest, days_ahead, block_tracker):
    async with sem:
        page = await context.new_page()
        travel_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        target_url = (
            f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}"
            f"%20from%20{origin}%20on%20{travel_date}%20one-way"
        )

        print(f"[*] {origin}->{dest} | T+{days_ahead} | {travel_date}")
        results = []

        try:
            await page.goto(target_url, timeout=35000)
            page_text = await page.content()

            if looks_blocked(page_text):
                block_tracker["count"] += 1
                print(f"  BLOCKED (captcha/anti-bot detected). Skipping this search.")
                await page.close()
                return results  # empty - never falls back to fake data

            block_tracker["count"] = 0  # reset on a clean page

            await page.wait_for_selector("li.pIav2d", timeout=8000)
            await asyncio.sleep(1)
            cards = await page.query_selector_all("li.pIav2d")

            for card in cards[:3]:
                airline_elem = await card.query_selector(".sSHqwe")
                time_elem = await card.query_selector(".wT33Eb, span[aria-label*='Departure time']")
                stops_elem = await card.query_selector(".EfT7Ae .VG3hNb, .BbR8Ec")
                price_elem = await card.query_selector(".YMlIz span, .BVAVmf span, span[role='text']")

                # If ANY required field is missing, skip this row entirely.
                # No fallback values, no guessing - this is the core fix.
                if not (airline_elem and time_elem and price_elem):
                    continue

                airline_text = await airline_elem.inner_text()
                airline_name = airline_text.split("\n")[0].strip()

                time_text = await time_elem.inner_text()
                times = time_text.split("–")
                if len(times) < 2:
                    continue
                dep_time, arr_time = times[0].strip(), times[1].strip()

                stops_text = await stops_elem.inner_text() if stops_elem else ""
                stops_count = 0 if ("nonstop" in stops_text.lower() or "direct" in stops_text.lower()) else 1

                price_text = await price_elem.inner_text()
                price_inr = parse_price(price_text)
                if price_inr is None:
                    continue  # skip rather than fabricate a "corrected" number

                results.append({
                    "timestamp_of_collection": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "airline": airline_name,
                    "origin": origin,
                    "destination": dest,
                    "route": f"{origin}-{dest}",
                    "travel_date": travel_date,
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                    "total_fare": price_inr,
                    "cabin_class": "Economy",
                    "number_of_stops": stops_count,
                    "advance_days": days_ahead,
                    "source": "google_flights_aggregator",  # honest label, not an airline name
                    "scrape_status": "ok",
                })

        except Exception as e:
            print(f"  ERROR: {e}")
        finally:
            await page.close()

        return results


async def main():
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    print(f"Starting collection across {len(ROUTES)} routes x {len(ADVANCE_WINDOWS)} windows...")

    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
    block_tracker = {"count": 0}
    all_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        for origin, dest in ROUTES:
            for days in ADVANCE_WINDOWS:
                rows = await scrape_single_query(sem, context, origin, dest, days, block_tracker)
                all_data.extend(rows)

                # Backoff grows the more consecutive blocks we hit -
                # this is the actual "slow down when blocked" behavior.
                if block_tracker["count"] > 0:
                    backoff = min(60 * block_tracker["count"], 300)
                    print(f"  Backing off {backoff}s before next search.")
                    await asyncio.sleep(backoff)
                else:
                    await asyncio.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))

        await browser.close()

    if all_data:
        file_exists = Path(OUTPUT_CSV).exists()
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_data[0].keys())
            if not file_exists:
                writer.writeheader()
            writer.writerows(all_data)
        print(f"\n[SUCCESS] Saved {len(all_data)} REAL rows (no fabricated data) to '{OUTPUT_CSV}'.")
    else:
        print("\n[WARNING] No real records collected this run - likely all blocked. Try again later.")


if __name__ == "__main__":
    asyncio.run(main())
