"""
Data model for a single scraped flight observation.

Every source adapter (mock_site.py, and later real sources) must produce
FlightOffer objects. This keeps the database and downstream analysis code
completely independent of which site the data came from.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class FlightOffer:
    source: str                        # e.g. "mock_site"
    origin: str                        # e.g. "DEL"
    destination: str                   # e.g. "BOM"
    departure_date: str                # "YYYY-MM-DD"

    airline: Optional[str] = None
    flight_number: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration: Optional[str] = None
    stops: Optional[int] = None
    cabin: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    provider: Optional[str] = None

    # Set automatically at insert time if not provided.
    observed_at: Optional[str] = None

    # SUCCESS, MISSING_FIELDS, CAPTCHA_DETECTED, NO_RESULTS, PARSE_ERROR
    scrape_status: str = "SUCCESS"

    def __post_init__(self):
        if self.observed_at is None:
            self.observed_at = (
                datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            )

    def to_dict(self) -> dict:
        return asdict(self)
