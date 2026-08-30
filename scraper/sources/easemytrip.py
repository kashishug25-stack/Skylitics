"""
Source adapter for EaseMyTrip (easemytrip.com) — the first live target.

IMPORTANT CONTEXT (read this before touching selectors):

EaseMyTrip's Terms & Conditions do NOT contain an explicit "no bots/scrapers/
automated queries" clause (unlike Wego, IndiGo, and Air India, all of which
were checked and ruled out — see README). Their terms do restrict copying
site content without permission, which is a real, non-zero residual risk —
this scraper should stay low-volume, respectful (rate-limited, no login,
no booking flow) and should never proceed past a CAPTCHA/challenge.

This adapter targets EaseMyTrip's route landing pages, which render flight
results directly without needing to drive the search form:

    https://www.easemytrip.com/flights/<origin-city>-<origin-code>-to-<dest-city>-<dest-code>/

e.g. https://www.easemytrip.com/flights/mumbai-bom-to-delhi-del/

Because exact CSS class names on this site are unknown (this file was
written without live DOM access), extraction here uses TEXT-PATTERN
matching rather than brittle class selectors:
  1. Find every "Book Now" button on the page (each flight card has one).
  2. Walk up to a reasonably-sized ancestor container for that button.
  3. Regex the airline / flight number / times / duration / stops / price
     out of that container's visible text.

This is more resilient to minor markup changes than guessing class names,
but it WILL need real debugging against the live page. Expect to adjust
the container-detection heuristic (how far up the DOM to walk) once you
see actual output — this is normal Stage 1 work, just happening on your
machine instead of in a controlled sandbox.
"""

import logging
import re
from typing import List, Optional

from playwright.sync_api import Page

from scraper.models import FlightOffer
from scraper.exceptions import CaptchaDetectedError, NoResultsError

logger = logging.getLogger("skylitics.sources.easemytrip")

SOURCE_NAME = "easemytrip"
BASE_URL = "https://www.easemytrip.com"

# City name -> (slug, IATA code) for building route URLs. Extend as needed.
CITY_SLUGS = {
    "DEL": "delhi-del",
    "BOM": "mumbai-bom",
    "BLR": "bangalore-blr",
    "HYD": "hyderabad-hyd",
}

# Known CAPTCHA / anti-bot signals across common providers. We only ever
# DETECT these — never attempt to solve or bypass them.
CAPTCHA_SIGNALS = [
    "text=Just a moment",              # Cloudflare interstitial
    "text=Verify you are human",
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "#challenge-running",              # Cloudflare
    "text=Access denied",
]

FLIGHT_NUMBER_RE = re.compile(r"\b([A-Z0-9]{1,3})\s*-\s*(\d{2,5})\b")
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2})\b")
DURATION_RE = re.compile(r"\b(\d{1,2}h\s?\d{0,2}m?)\b")
PRICE_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")
STOPS_RE = re.compile(r"\b(non-stop|1 stop|2 stops)\b", re.IGNORECASE)


def build_route_url(origin: str, destination: str) -> str:
    """e.g. build_route_url('DEL', 'BOM') -> .../flights/delhi-del-to-mumbai-bom/"""
    if origin not in CITY_SLUGS or destination not in CITY_SLUGS:
        raise ValueError(
            f"Unknown city code(s): {origin}, {destination}. "
            f"Add them to CITY_SLUGS in sources/easemytrip.py first."
        )
    origin_slug = CITY_SLUGS[origin]
    dest_slug = CITY_SLUGS[destination]
    return f"{BASE_URL}/flights/{origin_slug}-to-{dest_slug}/"


def detect_captcha(page: Page) -> bool:
    """Check for any known CAPTCHA/challenge signal. Never attempts to clear it."""
    for signal in CAPTCHA_SIGNALS:
        try:
            if page.locator(signal).count() > 0:
                return True
        except Exception:
            continue
    return False


def search(page: Page, origin: str, destination: str) -> None:
    """Navigate directly to the route's results page."""
    url = build_route_url(origin, destination)
    logger.info("Opening EaseMyTrip: %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)

    logger.info("Searching %s -> %s", origin, destination)

    # Give the results a moment to render (this is a real live site with
    # real network variability — a fixed short wait plus a content check
    # is more honest here than pretending we have a precise selector to
    # wait on, since we don't have confirmed DOM structure).
    page.wait_for_timeout(3000)

    if detect_captcha(page):
        raise CaptchaDetectedError("CAPTCHA/challenge detected on EaseMyTrip")


def extract_offers(
    page: Page,
    origin: str,
    destination: str,
    departure_date: str,
    cabin: str = "Economy",
) -> List[FlightOffer]:
    """
    Extract flight cards using the "Book Now" anchor technique described
    at the top of this file. Returns an empty list (not an error) if zero
    cards are found but the page loaded normally — caller decides whether
    that's a real NO_RESULTS case or a selector that needs adjusting.
    """
    # JS-side extraction: find each "Book Now" element, walk up a fixed
    # number of ancestor levels, grab that container's text. Tune
    # ANCESTOR_LEVELS if cards come back too broad (multiple flights
    # merged together) or too narrow (missing airline/price).
    ANCESTOR_LEVELS = 4

    raw_cards = page.evaluate(
        """
        (levels) => {
            const bookButtons = Array.from(document.querySelectorAll('*'))
                .filter(el => el.textContent.trim() === 'Book Now' && el.children.length === 0);
            const seen = new Set();
            const cards = [];
            for (const btn of bookButtons) {
                let node = btn;
                for (let i = 0; i < levels && node.parentElement; i++) {
                    node = node.parentElement;
                }
                const text = node.innerText;
                if (!seen.has(text)) {
                    seen.add(text);
                    cards.push(text);
                }
            }
            return cards;
        }
        """,
        ANCESTOR_LEVELS,
    )

    logger.info("Found %d candidate flight card(s) (Book Now anchors)", len(raw_cards))

    offers: List[FlightOffer] = []

    for card_text in raw_cards:
        airline = _guess_airline(card_text)
        flight_match = FLIGHT_NUMBER_RE.search(card_text)
        flight_number = f"{flight_match.group(1)}{flight_match.group(2)}" if flight_match else None

        times = TIME_RE.findall(card_text)
        departure_time = times[0] if len(times) >= 1 else None
        arrival_time = times[1] if len(times) >= 2 else None

        duration_match = DURATION_RE.search(card_text)
        duration = duration_match.group(1) if duration_match else None

        stops_match = STOPS_RE.search(card_text)
        stops = _parse_stops(stops_match.group(1) if stops_match else None)

        price_match = PRICE_RE.search(card_text)
        price = float(price_match.group(0).replace(",", "")) if price_match else None
        currency = "INR" if price is not None else None

        missing_required = airline is None or price is None

        if missing_required:
            logger.warning(
            "Skipping incomplete card — airline=%r price=%r | raw text: %.120r",
            airline,
            price,
            card_text,
            )
            continue

        status = "SUCCESS"
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
                stops=stops,
                cabin=cabin,
                price=price,
                currency=currency,
                provider="EaseMyTrip",
                scrape_status=status,
            )
        )

    logger.info("Extracted %d observation(s)", len(offers))

    if not offers:
        raise NoResultsError(f"No flight cards found for {origin}->{destination}")

    return offers


# Known airline names to match against card text. Extend as new ones appear.
KNOWN_AIRLINES = [
    "IndiGo", "Air India Express", "Air India", "AkasaAir", "Akasa Air",
    "SpiceJet", "Vistara", "GoAir", "Alliance Air", "Star Air", "Fly91",
]


def _guess_airline(card_text: str) -> Optional[str]:
    for name in KNOWN_AIRLINES:
        if name.lower() in card_text.lower():
            return name
    return None


def _parse_stops(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    raw = raw.lower()
    if "non-stop" in raw:
        return 0
    match = re.search(r"(\d+)", raw)
    return int(match.group(1)) if match else None
