"""
Orchestration layer: runs one complete search -> extract -> store cycle.

This is the file you'd call from a CLI entrypoint or, eventually, a scheduler.
It knows about browser lifecycle, the source adapter, and the database — but
none of the DOM/selector detail lives here.
"""

import logging
from typing import List

from scraper.browser import launch_browser
from scraper.database import init_db, insert_offers
from scraper.models import FlightOffer
from scraper.sources import mock_site
from scraper.exceptions import (
    CaptchaDetectedError,
    NoResultsError,
    SearchTimeoutError,
    UnexpectedPageStructureError,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger("skylitics.scraper")


def run_single_search(
    base_url: str,
    origin: str,
    destination: str,
    departure_date: str,
    passengers: int = 1,
    cabin: str = "Economy",
    headless: bool = True,
    allow_manual_captcha_solve: bool = False,
) -> List[FlightOffer]:
    """
    Run one full search against the mock site and return the FlightOffers
    that were inserted into SQLite. Returns an empty list on any handled
    failure (CAPTCHA, no results, timeout, etc.) rather than raising, so a
    batch runner can continue to the next route/date.
    """
    logger.info("Starting scraper")
    init_db()

    offers: List[FlightOffer] = []

    try:
        with launch_browser(headless=headless) as page:
            mock_site.search(
                page, base_url, origin, destination, departure_date,
                passengers=passengers, cabin=cabin,
            )

            outcome = mock_site.wait_for_outcome(page)
            logger.info("Results page loaded (outcome=%s)", outcome)

            if outcome == "captcha":
                cleared = mock_site.handle_captcha(page, allow_manual_captcha_solve)
                if not cleared:
                    raise CaptchaDetectedError("CAPTCHA could not be cleared")
                outcome = "results"

            if outcome == "error":
                raise UnexpectedPageStructureError(
                    "Results area did not match any known state"
                )

            if outcome == "empty":
                raise NoResultsError(f"No flights found for {origin}->{destination}")

            offers = mock_site.extract_offers(page, origin, destination, departure_date, cabin)

    except CaptchaDetectedError as exc:
        logger.warning("CAPTCHA handling ended the run: %s", exc)
        return []
    except NoResultsError as exc:
        logger.warning(str(exc))
        return []
    except SearchTimeoutError as exc:
        logger.error("Search results failed to load: %s", exc)
        return []
    except UnexpectedPageStructureError as exc:
        logger.error("Unexpected page structure: %s", exc)
        return []
    except Exception as exc:  # noqa: BLE001 - top-level safety net, always logged
        logger.error("Unhandled scraper error: %s", exc)
        return []

    if offers:
        insert_offers(offers)

    logger.info("Scrape completed")
    return offers


if __name__ == "__main__":
    import sys

    # file:// URL to the local mock site — see README for how to serve it
    # over http:// instead, which behaves more like a real target.
    default_url = "http://localhost:8000/mock_site/index.html"
    url = sys.argv[1] if len(sys.argv) > 1 else default_url

    run_single_search(
        base_url=url,
        origin="DEL",
        destination="BOM",
        departure_date="2026-09-15",
        passengers=1,
        cabin="Economy",
        headless=True,
    )
