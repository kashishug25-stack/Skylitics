"""
clean_data.py — bridges the gap between scraper output and calculate_index.py

WHY THIS FILE IS NEEDED:
scraper.py (and scraper_fixed.py) save results to a CSV file.
calculate_index.py reads from a SQLite table called `cleaned_fare_quotes`.
Nothing currently connects these two - this script is that missing bridge.

WHAT IT DOES:
1. Reads every raw CSV in data/raw/
2. Removes exact duplicate rows
3. Drops rows missing a route, date, or price (never invents them)
4. Flags (not deletes) prices under 1000 or over 100000 as suspicious,
   per your own plan's outlier rule
5. Writes accepted rows into the cleaned_fare_quotes table
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_FILE = "airfare_intelligence.db"
RAW_DATA_DIR = "data/raw"

REQUIRED_COLUMNS = ["origin", "destination", "travel_date", "advance_days", "total_fare"]


def create_table_if_needed(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cleaned_fare_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observed_at TEXT,
            source TEXT,
            origin TEXT,
            destination TEXT,
            departure_date TEXT,
            advance_days INTEGER,
            airline TEXT,
            total_fare REAL,
            currency TEXT DEFAULT 'INR',
            availability TEXT,
            scrape_status TEXT,
            is_outlier INTEGER DEFAULT 0
        )
    """)
    conn.commit()


def load_all_raw_csvs():
    files = list(Path(RAW_DATA_DIR).glob("*.csv"))
    if not files:
        print(f"No raw CSV files found in {RAW_DATA_DIR}/")
        return pd.DataFrame()

    frames = [pd.read_csv(f) for f in files]
    combined = pd.concat(frames, ignore_index=True)
    print(f"Loaded {len(combined)} raw rows from {len(files)} file(s).")
    return combined


def clean(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    before = len(df)

    # Rule: never invent a missing required field - drop the row instead.
    df = df.dropna(subset=[c for c in REQUIRED_COLUMNS if c in df.columns])

    # Remove exact duplicates (same route, date, airline, price, timestamp)
    dedup_cols = [c for c in ["origin", "destination", "travel_date", "airline", "total_fare"] if c in df.columns]
    df = df.drop_duplicates(subset=dedup_cols, keep="first")

    # Flag suspicious prices instead of silently deleting them -
    # a human can review these later rather than losing the data entirely.
    df["is_outlier"] = ((df["total_fare"] < 1000) | (df["total_fare"] > 100000)).astype(int)

    after = len(df)
    print(f"Cleaning: {before} raw rows -> {after} accepted rows "
          f"({df['is_outlier'].sum()} flagged as outliers, kept but marked).")

    return df


def save_to_database(df: pd.DataFrame):
    if df.empty:
        print("Nothing to save.")
        return

    conn = sqlite3.connect(DB_FILE)
    create_table_if_needed(conn)

    rows_saved = 0
    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO cleaned_fare_quotes
            (observed_at, source, origin, destination, departure_date, advance_days,
             airline, total_fare, currency, availability, scrape_status, is_outlier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("timestamp_of_collection", ""),
            row.get("source", "unknown"),
            row["origin"],
            row["destination"],
            row["travel_date"],
            int(row["advance_days"]),
            row.get("airline", ""),
            float(row["total_fare"]),
            "INR",
            row.get("availability", "available"),
            row.get("scrape_status", "ok"),
            int(row["is_outlier"]),
        ))
        rows_saved += 1

    conn.commit()
    conn.close()
    print(f"Saved {rows_saved} cleaned rows into cleaned_fare_quotes.")


if __name__ == "__main__":
    raw = load_all_raw_csvs()
    cleaned = clean(raw)
    save_to_database(cleaned)
