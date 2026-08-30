"""
Source adapter for the local SkyMock test environment (mock_site/index.html).

This is the file that will eventually be swapped out / duplicated per real
source (e.g. sources/some_airline.py) once a permitted live target is
confirmed. Everything in scraper.py, models.py, and database.py stays the
same regardless of source.
"""

import logging
import re
from typing import List

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from scraper.models import FlightOffer
from scraper.selectors import MOCK_SITE as SEL
from scraper.exceptions import (
    CaptchaDetectedError,
    NoResultsError,
    UnexpectedPageStructureError,
    SearchTimeoutError,
)

logger = logging.getLogger("skylitics.sources.mock_site")

SOURCE_NAME = "mock_site"


def search(
    page: Page,
    base_url: str,
    origin: str,
    destination: str,
    departure_date: str,
    passengers: int = 1,
    cabin: str = "Economy",
) -> None:
    """Navigate to the site and submit a search. Raises on failure."""
    logger.info("Opening %s", base_url)
    page.goto(base_url)

    logger.info("Searching %s -> %s", origin, destination)
    page.fill(SEL["origin_input"], origin)
    page.fill(SEL["destination_input"], destination)
    page.fill(SEL["date_input"], departure_date)
    page.select_option(SEL["passengers_select"], str(passengers))
    page.select_option(SEL["cabin_select"], cabin)

    logger.info("Travel date: %s", departure_date)
    page.click(SEL["search_button"])


def wait_for_outcome(page: Page, timeout_ms: int = 15_000) -> str:
    """
    Wait for the page to settle into one of four known states, and return
    which one occurred: "results", "empty", "captcha", or "error".

    Raises SearchTimeoutError if none of the known states appear in time.
    """
    # NOTE: a single wait_for_selector() with a comma-separated CSS selector
    # list does NOT mean "wait for any of these to be visible" — Playwright
    # resolves it to a multi-element locator and waits for the FIRST DOM
    # match specifically, which can be the wrong (hidden) element. We poll
    # each known outcome selector in JS instead, which correctly checks
    # "is any one of these currently visible".
    js_check = """
        ([resultsSel, noResultsSel, captchaSel, errorSel]) => {
            const isVisible = (sel) => {
                const el = document.querySelector(sel);
                return !!(el && el.offsetParent !== null);
            };
            if (isVisible(resultsSel)) return "results";
            if (isVisible(noResultsSel)) return "empty";
            if (isVisible(captchaSel)) return "captcha";
            if (isVisible(errorSel)) return "error";
            return null;
        }
    """
    try:
        page.wait_for_function(
            js_check,
            arg=[SEL["results_list"], SEL["no_results"], SEL["captcha_block"], SEL["unexpected_error"]],
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError as exc:
        raise SearchTimeoutError(
            f"No known result state appeared within {timeout_ms}ms"
        ) from exc

    if page.is_visible(SEL["captcha_block"]):
        return "captcha"
    if page.is_visible(SEL["unexpected_error"]):
        return "error"
    if page.is_visible(SEL["no_results"]):
        return "empty"
    if page.is_visible(SEL["results_list"]):
        return "results"

    raise UnexpectedPageStructureError("Reached wait_for_outcome with no matching state")


def _parse_price(raw_text: str):
    """
    Extract a numeric price from text like '₹4,820'. Returns (price, currency).
    Never invents a value — returns (None, None) if nothing parseable is found.
    """
    if not raw_text:
        return None, None
    digits = re.sub(r"[^\d.]", "", raw_text)
    if not digits:
        return None, None
    try:
        price = float(digits)
    except ValueError:
        return None, None
    currency = "INR" if "₹" in raw_text else None
    return price, currency


def _parse_stops(raw_text: str):
    if not raw_text:
        return None
    if "non-stop" in raw_text.lower():
        return 0
    match = re.search(r"(\d+)", raw_text)
    return int(match.group(1)) if match else None


def extract_offers(
    page: Page,
    origin: str,
    destination: str,
    departure_date: str,
    cabin: str,
) -> List[FlightOffer]:
    """
    Locate all flight cards on the page and turn each into a FlightOffer.
    Works whether there are 2 cards or 50 — no hard-coded indices.
    """
    cards = page.query_selector_all(SEL["flight_card"])
    logger.info("Found %d flight cards", len(cards))

    offers: List[FlightOffer] = []

    for card in cards:
        def field(selector_key: str) -> str:
            el = card.query_selector(SEL[selector_key])
            return el.inner_text().strip() if el else ""

        airline = field("field_airline") or None
        flight_number = field("field_flight_number") or None
        departure_time = field("field_departure_time") or None
        arrival_time = field("field_arrival_time") or None
        duration = field("field_duration") or None
        stops_raw = field("field_stops")
        price_raw = field("field_price")
        currency_field = field("field_currency")
        provider = field("field_provider") or None

        price, parsed_currency = _parse_price(price_raw)
        currency = currency_field or parsed_currency

        missing_required = airline is None or price is None
        status = "MISSING_FIELDS" if missing_required else "SUCCESS"
        if missing_required:
            logger.warning(
                "Card missing required field(s) — airline=%r price_raw=%r",
                airline, price_raw,
            )

        offers.append(
            FlightOffer(
                source=SOURCE_NAME,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                airline=airline,
                flight_number=flight_number,
                departure_time=departure_time,
                arrival_time=arrival_time,
                duration=duration,
                stops=_parse_stops(stops_raw),
                cabin=cabin,
                price=price,
                currency=currency,
                provider=provider,
                scrape_status=status,
            )
        )

    logger.info("Extracted %d observation(s)", len(offers))
    return offers


def handle_captcha(page: Page, allow_manual_solve: bool) -> bool:
    """
    A CAPTCHA/challenge was detected. Per policy we never bypass it.

    If allow_manual_solve is True, we pause and wait for a human to clear it
    (useful when running headless=False locally). Returns True if the
    challenge was cleared and results appeared, False otherwise.
    """
    logger.warning("CAPTCHA detected")
    if not allow_manual_solve:
        logger.warning("Manual solve not permitted for this run — terminating source")
        return False

    logger.info("Waiting for manual CAPTCHA completion (up to 60s)...")
    try:
        page.wait_for_selector(SEL["results_list"], state="visible", timeout=60_000)
        logger.info("CAPTCHA cleared manually, results loaded")
        return True
    except PlaywrightTimeoutError:
        logger.error("CAPTCHA was not cleared manually within the allotted time")
        return False
