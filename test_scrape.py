import asyncio
import re
from playwright.async_api import async_playwright

def clean_num(val_str: str) -> float:
    if not val_str:
        return 0.0
    digits = re.sub(r"[^\d.]", "", val_str)
    return float(digits) if digits else 0.0

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(locale="en-IN", viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        url = "https://www.google.com/travel/flights?q=Flights%20to%20BOM%20from%20DEL%20on%202026-09-07%20oneway&curr=INR&hl=en"
        print("[*] Navigating to Google Flights (DEL -> BOM)...")
        
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(3.0)

        # Scroll down to load all carriers (Akasa, Air India, SpiceJet, IndiGo)
        print("[*] Scrolling to load all scheduled airlines...")
        for scroll_y in [600, 1400, 2400]:
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await asyncio.sleep(1.0)

        # Query all cards
        flight_elements = await page.query_selector_all('li.pIav2d, div.yR1fYc, div.eO2Zfd')
        print(f"\n[+] Found {len(flight_elements)} raw flight card elements on page.\n")

        extracted_count = 0
        for idx, el in enumerate(flight_elements):
            text = await el.inner_text()
            if not text or ("₹" not in text and "INR" not in text):
                continue

            # Price
            price_match = re.search(r"₹\s*([\d,]+)", text)
            if not price_match:
                continue
            fare = clean_num(price_match.group(1))

            # Times
            time_match = re.search(r"(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[–\-]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?(?:\+\d)?)", text, re.IGNORECASE)
            if not time_match:
                continue
            dep_time, arr_time = time_match.group(1).strip(), time_match.group(2).strip()

            # Airline
            airline = "Scheduled Airline"
            logo_img = await el.query_selector('img[alt]')
            img_alt = await logo_img.get_attribute('alt') if logo_img else ""
            
            for name in ["Air India Express", "Air India", "Akasa Air", "SpiceJet", "IndiGo"]:
                if name.lower() in img_alt.lower() or name.lower() in text.lower():
                    airline = name
                    break

            # Duration & Stops
            dur_match = re.search(r"(\d+\s*hr(?:\s*\d+\s*min)?)", text)
            duration = dur_match.group(1) if dur_match else "2 hr 15 min"
            stops = "1 Stop" if ("1 stop" in text.lower() or "stop" in text.lower()) and "nonstop" not in text.lower() else "Nonstop"

            extracted_count += 1
            print(f"[{extracted_count}] {airline.ljust(18)} | {dep_time.ljust(9)} -> {arr_time.ljust(10)} | {duration.ljust(12)} | {stops.ljust(8)} | ₹{int(fare):,}")

        print(f"\n[✔] Extracted {extracted_count} total flights successfully.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
    