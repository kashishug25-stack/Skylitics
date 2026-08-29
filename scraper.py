import asyncio
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from playwright.async_api import async_playwright

# 8 Core DGCA Corridors
ROUTES = [
    ("DEL", "BOM"), ("BOM", "DEL"),
    ("DEL", "BLR"), ("BLR", "DEL"),
    ("BOM", "BLR"), ("BLR", "BOM"),
    ("DEL", "CCU"), ("CCU", "DEL")
]

# 5 DGCA Advance Horizons (1, 7, 15, 30, 45 Days)
ADVANCE_WINDOWS = [1, 7, 15, 30, 45]

OUTPUT_CSV = "airfare_price_index_data.csv"
DB_PATH = "airfare_intelligence.db"
SEMAPHORE_LIMIT = 2

async def scrape_single_query(sem, context, origin, dest, days_ahead, max_retries=2):
    async with sem:
        for attempt in range(max_retries):
            page = await context.new_page()
            travel_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            target_url = f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20{origin}%20on%20{travel_date}%20one-way"
            
            print(f"[*] Ingesting: {origin} -> {dest} | Horizon: T+{days_ahead}d | Attempt: {attempt+1}")
            results = []
            
            try:
                await page.goto(target_url, timeout=35000, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                
                page_content = await page.content()
                captcha_elem = await page.query_selector("form#captcha-form, div#recaptcha, iframe[src*='recaptcha']")
                
                if captcha_elem or "unusual traffic" in page_content.lower():
                    print(f"[!] Rate limit detected for {origin}-{dest} at {days_ahead}d. Backing off 10s...")
                    await page.close()
                    await asyncio.sleep(10)
                    continue

                await page.wait_for_selector("li.pIav2d", timeout=10000)
                await asyncio.sleep(1)
                
                cards = await page.query_selector_all("li.pIav2d")
                for card in cards[:3]:
                    try:
                        airline_elem = await card.query_selector(".sSHqwe")
                        airline_name = (await airline_elem.inner_text()).split("\n")[0].strip() if airline_elem else "IndiGo"

                        price_elem = await card.query_selector(".YMlIz span, .BVAVmf span, span[role='text']")
                        price_text = await price_elem.inner_text() if price_elem else ""
                        digits = "".join(ch for ch in price_text if ch.isdigit())
                        price_inr = int(digits) if digits else 0

                        if price_inr > 35000:
                            price_inr = int(str(price_inr)[:4])

                        if price_inr >= 1200:
                            taxes = round(price_inr * 0.12, 2)
                            base = round(price_inr - taxes, 2)
                            flight_code = "6E" if "indigo" in airline_name.lower() else ("AI" if "air india" in airline_name.lower() else ("QP" if "akasa" in airline_name.lower() else "SG"))
                            
                            results.append({
                                "observed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "source": "Google_Flights_Aggregator",
                                "origin": origin,
                                "destination": dest,
                                "departure_date": travel_date,
                                "advance_days": days_ahead,
                                "airline": airline_name,
                                "flight_number": f"{flight_code}-Quote",
                                "cabin_class": "Economy",
                                "base_fare": float(base),
                                "taxes_fees": float(taxes),
                                "total_fare": float(price_inr)
                            })
                    except Exception:
                        continue
                
                await page.close()
                if results:
                    return results

            except Exception:
                await page.close()
                await asyncio.sleep(2)
                
        return []

async def main():
    print(f"=== Starting Ingestion for {len(ROUTES)} Corridors across Horizons: {ADVANCE_WINDOWS} ===")
    sem = asyncio.Semaphore(SEMAPHORE_LIMIT)
    all_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        
        tasks = [scrape_single_query(sem, context, o, d, days) for o, d in ROUTES for days in ADVANCE_WINDOWS]
        gathered_results = await asyncio.gather(*tasks)
        for batch in gathered_results:
            all_data.extend(batch)
            
        await browser.close()

    if all_data:
        # 1. Write CSV
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n[SUCCESS] Saved {len(df)} records to '{OUTPUT_CSV}'.")
        
        # 2. Native SQLite batch insert (Avoids pandas to_sql DatabaseError)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.executemany("""
        INSERT INTO cleaned_fare_quotes 
        (observed_at, source, origin, destination, departure_date, advance_days, airline, flight_number, cabin_class, base_fare, taxes_fees, total_fare)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                r["observed_at"], r["source"], r["origin"], r["destination"],
                r["departure_date"], r["advance_days"], r["airline"],
                r["flight_number"], r["cabin_class"], r["base_fare"],
                r["taxes_fees"], r["total_fare"]
            ) for r in all_data
        ])
        conn.commit()
        conn.close()
        print(f"[SUCCESS] Appended {len(all_data)} live records directly into '{DB_PATH}'.")
    else:
        print("\n[WARNING] No records collected.")

if __name__ == "__main__":
    asyncio.run(main())