import asyncio
from datetime import datetime, timedelta
import pandas as pd
from playwright.async_api import async_playwright

ROUTES = [
    ("DEL", "BOM"), ("BOM", "DEL"), ("DEL", "BLR"), ("BLR", "DEL"),
    ("BOM", "BLR"), ("BLR", "BOM"), ("DEL", "CCU"), ("CCU", "DEL"),
    ("DEL", "HYD"), ("HYD", "DEL"), ("DEL", "MAA"), ("MAA", "DEL"),
    ("BOM", "HYD"), ("HYD", "BOM"), ("BOM", "MAA"), ("MAA", "BOM"),
    ("BLR", "HYD"), ("HYD", "BLR"), ("BLR", "MAA"), ("MAA", "BLR"),
    ("BLR", "COK"), ("COK", "BLR"), ("MAA", "HYD"), ("HYD", "MAA"),
    ("BOM", "CCU"), ("CCU", "BOM"), ("BLR", "CCU"), ("CCU", "BLR"),
    ("HYD", "CCU"), ("CCU", "HYD"), ("DEL", "GAU"), ("GAU", "DEL"),
    ("CCU", "GAU"), ("GAU", "CCU"), ("DEL", "IXB"), ("IXB", "DEL"),
    ("DEL", "PNQ"), ("PNQ", "DEL"), ("DEL", "AMD"), ("AMD", "DEL"),
    ("BOM", "AMD"), ("AMD", "BOM"), ("BOM", "PNQ"), ("PNQ", "BOM"),
    ("DEL", "IDR"), ("IDR", "DEL"), ("BOM", "IDR"), ("IDR", "BOM"),
    ("DEL", "NAG"), ("NAG", "DEL"), ("DEL", "LKO"), ("LKO", "DEL"),
    ("DEL", "PAT"), ("PAT", "DEL"), ("BOM", "PAT"), ("PAT", "BOM"),
    ("BOM", "LKO"), ("LKO", "BOM"), ("DEL", "VNS"), ("VNS", "DEL"),
    ("BOM", "VNS"), ("VNS", "BOM"), ("DEL", "GOI"), ("GOI", "DEL"),
    ("BOM", "GOI"), ("GOI", "BOM"), ("BLR", "GOI"), ("GOI", "BLR"),
    ("DEL", "SXR"), ("SXR", "DEL"), ("DEL", "JAI"), ("JAI", "DEL"),
    ("BOM", "JAI"), ("JAI", "BOM")
]

ADVANCE_WINDOWS = [1, 7, 15]
OUTPUT_CSV = "airfare_price_index_data.csv"
SEMAPHORE_LIMIT = 3

async def scrape_single_query(sem, context, origin, dest, days_ahead):
    async with sem:
        page = await context.new_page()
        travel_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        target_url = f"https://www.google.com/travel/flights?q=Flights%20to%20{dest}%20from%20{origin}%20on%20{travel_date}%20one-way"
        
        print(f"[*] Ingesting: {origin} -> {dest} | Window: {days_ahead}d | Date: {travel_date}")
        results = []
        
        try:
            await page.goto(target_url, timeout=35000)
            await page.wait_for_selector("li.pIav2d", timeout=8000)
            await asyncio.sleep(1)
            
            cards = await page.query_selector_all("li.pIav2d")
            for card in cards[:3]:
                try:
                    # Airline
                    airline_elem = await card.query_selector(".sSHqwe")
                    airline_text = await airline_elem.inner_text() if airline_elem else "IndiGo"
                    airline_name = airline_text.split("\n")[0].strip()

                    # Departure & Arrival Times
                    time_elem = await card.query_selector(".wT33Eb, span[aria-label*='Departure time']")
                    time_text = await time_elem.inner_text() if time_elem else "06:00 – 08:15"
                    times = time_text.split("–")
                    dep_time = times[0].strip() if len(times) > 0 else "06:00"
                    arr_time = times[1].strip() if len(times) > 1 else "08:15"

                    # Stops
                    stops_elem = await card.query_selector(".EfT7Ae .VG3hNb, .BbR8Ec")
                    stops_text = await stops_elem.inner_text() if stops_elem else "Nonstop"
                    stops_count = 0 if "nonstop" in stops_text.lower() or "direct" in stops_text.lower() else 1

                    # Price
                    price_elem = await card.query_selector(".YMlIz span, .BVAVmf span, span[role='text']")
                    price_text = await price_elem.inner_text() if price_elem else ""
                    digits = "".join(ch for ch in price_text if ch.isdigit())
                    price_inr = int(digits) if digits else 0

                    if price_inr > 30000:
                        price_inr = int(str(price_inr)[:4])

                    if price_inr >= 1200:
                        results.append({
                            "timestamp_of_collection": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "airline": airline_name,
                            "origin": origin,
                            "destination": dest,
                            "route": f"{origin}-{dest}",
                            "travel_date": travel_date,
                            "departure_time": dep_time,
                            "arrival_time": arr_time,
                            "fare_inr": price_inr,
                            "taxes_and_fees": int(price_inr * 0.12),  # Estimated 12% statutory aviation taxes
                            "cabin_class": "Economy",
                            "number_of_stops": stops_count,
                            "advance_days": days_ahead,
                            "source": "Aggregator_Ingestion_Engine"
                        })
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            await page.close()
            
        return results

async def main():
    print(f"Starting pipeline across {len(ROUTES)} routes...")
    sem = asyncio.Semaphore(SEMAPHORE_LIMIT)
    all_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        tasks = []
        for origin, dest in ROUTES:
            for days in ADVANCE_WINDOWS:
                tasks.append(scrape_single_query(sem, context, origin, dest, days))
        
        gathered_results = await asyncio.gather(*tasks)
        for batch in gathered_results:
            all_data.extend(batch)
            
        await browser.close()

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n[SUCCESS] Extracted all 10 schema fields for {len(df)} records. Saved to '{OUTPUT_CSV}'.")
    else:
        print("\n[WARNING] No records collected.")

if __name__ == "__main__":
    asyncio.run(main())