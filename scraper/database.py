"""
SQLite storage layer. This is the ONLY place that touches airfare.db directly.

Design rule: every scrape observation is a new row. We never UPDATE or
overwrite a previous price observation, because Skylitics needs the full
history to compute an airfare index over time.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Iterable

from scraper.models import FlightOffer

logger = logging.getLogger("skylitics.database")

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "airfare.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS flights (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    airline         TEXT,
    flight_number   TEXT,
    origin          TEXT NOT NULL,
    destination     TEXT NOT NULL,
    departure_date  TEXT NOT NULL,
    departure_time  TEXT,
    arrival_time    TEXT,
    duration        TEXT,
    stops           INTEGER,
    cabin           TEXT,
    price           REAL,
    currency        TEXT,
    provider        TEXT,
    observed_at     TEXT NOT NULL,
    scrape_status   TEXT NOT NULL
);
"""

# Speeds up the time-series queries Skylitics will eventually run
# ("how has DEL->BOM economy priced moved over time").
INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_flights_route_date ON flights (origin, destination, departure_date);",
    "CREATE INDEX IF NOT EXISTS idx_flights_observed_at ON flights (observed_at);",
]


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(SCHEMA)
        for stmt in INDEX_STATEMENTS:
            conn.execute(stmt)
        conn.commit()
        logger.info("Database initialized at %s", db_path)
    finally:
        conn.close()


def insert_offer(offer: FlightOffer, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Insert a single FlightOffer as a new row. Returns the new row id."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO flights (
                source, airline, flight_number, origin, destination,
                departure_date, departure_time, arrival_time, duration,
                stops, cabin, price, currency, provider, observed_at, scrape_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer.source, offer.airline, offer.flight_number, offer.origin,
                offer.destination, offer.departure_date, offer.departure_time,
                offer.arrival_time, offer.duration, offer.stops, offer.cabin,
                offer.price, offer.currency, offer.provider, offer.observed_at,
                offer.scrape_status,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def insert_offers(offers: Iterable[FlightOffer], db_path: Path = DEFAULT_DB_PATH) -> int:
    """Bulk insert. Returns the number of rows inserted."""
    count = 0
    conn = get_connection(db_path)
    try:
        for offer in offers:
            conn.execute(
                """
                INSERT INTO flights (
                    source, airline, flight_number, origin, destination,
                    departure_date, departure_time, arrival_time, duration,
                    stops, cabin, price, currency, provider, observed_at, scrape_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    offer.source, offer.airline, offer.flight_number, offer.origin,
                    offer.destination, offer.departure_date, offer.departure_time,
                    offer.arrival_time, offer.duration, offer.stops, offer.cabin,
                    offer.price, offer.currency, offer.provider, offer.observed_at,
                    offer.scrape_status,
                ),
            )
            count += 1
        conn.commit()
        logger.info("Inserted %d observation(s) into SQLite", count)
        return count
    finally:
        conn.close()


def fetch_all(db_path: Path = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT * FROM flights ORDER BY observed_at DESC").fetchall()
    finally:
        conn.close()


def count_rows(db_path: Path = DEFAULT_DB_PATH) -> int:
    conn = get_connection(db_path)
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM flights").fetchone()["c"]
    finally:
        conn.close()
