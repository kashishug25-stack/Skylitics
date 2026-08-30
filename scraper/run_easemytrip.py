"""
Standalone runner for the live EaseMyTrip source.

Kept separate from scraper.py (which orchestrates the mock_site run) because
this one has real-world concerns the mock site doesn't: CAPTCHA handling
policy, rate limiting between routes, and the fact that we genuinely don't
know the DOM will behave until we see it live.

Usage:
    python -m scraper.run_easemytrip DEL BOM
    python -m scraper.run_easemytrip DEL BOM --headed      # watch it run
    python -m scraper.run_easemytrip DEL BOM --show-cards  # print raw extracted text for debugging
"""

import argparse
import logging
import time
from datetime import date, timedelta

from scraper.browser import launch_browser
from scraper.database import init_db, insert_offers
from scraper.sources import easemytrip
from scraper.exceptions import CaptchaDetectedError, NoResultsError

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("skylitics.run_easemytrip")

# Be a polite scraper: EaseMyTrip's terms don't ban automation outright, but
# there's no reason to hammer them. Wait this long between route requests.
POLITE_DELAY_SECONDS = 5


def run(origin: str, destination: str, headless: bool = True, show_cards: bool = False):
    init_db()
    departure_date = (date.today() + timedelta(days=15)).isoformat()  # arbitrary T+15 for now

    logger.info("Starting EaseMyTrip live scrape: %s -> %s", origin, destination)

    with launch_browser(headless=headless) as page:
        try:
            easemytrip.search(page, origin, destination)
        except CaptchaDetectedError as exc:
            logger.warning("CAPTCHA detected during search — stopping, not attempting bypass: %s", exc)
            return []

        if show_cards:
            # Debug mode: dump the raw "Book Now" ancestor text so you can see
            # exactly what the extraction regexes are working with, and tune
            # ANCESTOR_LEVELS in sources/easemytrip.py if needed.
            raw = page.evaluate(
                """() => Array.from(document.querySelectorAll('*'))
                    .filter(el => el.textContent.trim() === 'Book Now' && el.children.length === 0)
                    .slice(0, 3)
                    .map(btn => {
                        let node = btn;
                        for (let i = 0; i < 4 && node.parentElement; i++) node = node.parentElement;
                        return node.innerText;
                    })"""
            )
            for i, card in enumerate(raw):
                print(f"\n--- candidate card {i} (first 400 chars) ---\n{card[:400]}")
            return []

        try:
            offers = easemytrip.extract_offers(page, origin, destination, departure_date)
        except NoResultsError as exc:
            logger.warning(str(exc))
            return []

    if offers:
        insert_offers(offers)

    logger.info("Scrape completed: %d observation(s)", len(offers))
    return offers


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape live flight data from EaseMyTrip")
    parser.add_argument("origin", help="Origin IATA code, e.g. DEL")
    parser.add_argument("destination", help="Destination IATA code, e.g. BOM")
    parser.add_argument("--headed", action="store_true", help="Show the browser window")
    parser.add_argument("--show-cards", action="store_true", help="Debug: print raw card text instead of inserting to DB")
    args = parser.parse_args()

    run(
        args.origin.upper(),
        args.destination.upper(),
        headless=not args.headed,
        show_cards=args.show_cards,
    )
