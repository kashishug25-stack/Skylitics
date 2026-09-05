"""
seed_database.py — VimanSuchak / Skylitics Intelligence Data Engine
Initializes SQLite schema, assigns DGCA traffic weights, and seeds baseline observations.
"""

import sqlite3
import datetime
import random

DB_FILE = "airfare_intelligence.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 1. DGCA Route Basket Table (with real traffic weights)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS route_basket (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        route_name TEXT NOT NULL,
        annual_pax INTEGER NOT NULL,
        route_weight REAL NOT NULL,
        base_tariff_inr REAL NOT NULL,
        is_active INTEGER DEFAULT 1
    )
    """)

    # 2. Raw Ingested Quotes Table (Scraper output)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_fare_quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        observed_at TIMESTAMP NOT NULL,
        source TEXT NOT NULL,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        departure_date TEXT NOT NULL,
        advance_days INTEGER NOT NULL,
        airline TEXT NOT NULL,
        flight_number TEXT NOT NULL,
        stops TEXT NOT NULL,
        cabin_class TEXT NOT NULL,
        base_fare REAL,
        taxes_fees REAL,
        total_fare REAL NOT NULL,
        scrape_status TEXT DEFAULT 'success'
    )
    """)

    # 3. Cleaned Quotes Table (Deduplicated & Outlier Filtered)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cleaned_fare_quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_quote_id INTEGER,
        observed_at TIMESTAMP NOT NULL,
        source TEXT NOT NULL,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        departure_date TEXT NOT NULL,
        advance_days INTEGER NOT NULL,
        airline TEXT NOT NULL,
        flight_number TEXT NOT NULL,
        cabin_class TEXT NOT NULL,
        base_fare REAL NOT NULL,
        taxes_fees REAL NOT NULL,
        total_fare REAL NOT NULL,
        FOREIGN KEY (raw_quote_id) REFERENCES raw_fare_quotes(id)
    )
    """)

    # 4. Computed Laspeyres Index Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS computed_price_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        computed_at TIMESTAMP NOT NULL,
        corridor TEXT NOT NULL,
        advance_days INTEGER NOT NULL,
        median_fare REAL NOT NULL,
        base_fare REAL NOT NULL,
        price_relative REAL NOT NULL,
        laspeyres_index REAL NOT NULL,
        surge_status TEXT NOT NULL
    )
    """)

    conn.commit()
    return conn

def seed_data(conn):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM route_basket")
    cursor.execute("DELETE FROM raw_fare_quotes")
    cursor.execute("DELETE FROM cleaned_fare_quotes")
    cursor.execute("DELETE FROM computed_price_index")

    # Real DGCA Passenger Traffic Distribution (Top 8 Indian Corridors)
    routes = [
        ("DEL", "BOM", "Delhi - Mumbai", 6850000, 4600),
        ("DEL", "BLR", "Delhi - Bengaluru", 4920000, 5200),
        ("BOM", "BLR", "Mumbai - Bengaluru", 3890000, 3800),
        ("DEL", "CCU", "Delhi - Kolkata", 3450000, 4800),
        ("BLR", "HYD", "Bengaluru - Hyderabad", 2980000, 3100),
        ("MAA", "DEL", "Chennai - Delhi", 2840000, 5100),
        ("DEL", "GOI", "Delhi - Goa", 2650000, 4900),
        ("DEL", "PAT", "Delhi - Patna", 2220000, 4300)
    ]

    total_pax = sum(r[3] for r in routes)

    for o, d, name, pax, base in routes:
        weight = round(pax / total_pax, 4)
        cursor.execute("""
        INSERT INTO route_basket (origin, destination, route_name, annual_pax, route_weight, base_tariff_inr)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (o, d, name, pax, weight, base))

    # Airlines & Carriers
    airlines = [
        ("IndiGo", "6E", 0.98),
        ("Air India", "AI", 1.05),
        ("Akasa Air", "QP", 0.94),
        ("SpiceJet", "SG", 1.01),
        ("Air India Express", "IX", 0.93)
    ]

    sources = ["IndiGo Direct", "Cleartrip OTA", "Ixigo Aggregator"]
    horizons = [1, 7, 15, 30, 45]
    horizon_factors = {1: 1.52, 7: 1.14, 15: 0.95, 30: 0.88, 45: 0.84}

    now = datetime.datetime.now()

    for o, d, name, pax, base_price in routes:
        for days in horizons:
            flight_date = (now + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
            base_corridor_fare = base_price * horizon_factors[days]

            for air_name, code, factor in airlines:
                flight_no = f"{code}-{random.randint(100, 999)}"
                fare = round(base_corridor_fare * factor + random.randint(-120, 120))
                taxes = round(fare * 0.22)
                pure_base = fare - taxes
                source = random.choice(sources)

                cursor.execute("""
                INSERT INTO raw_fare_quotes 
                (observed_at, source, origin, destination, departure_date, advance_days, airline, flight_number, stops, cabin_class, base_fare, taxes_fees, total_fare)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (now.isoformat(), source, o, d, flight_date, days, air_name, flight_no, "Nonstop", "Economy", pure_base, taxes, fare))

                raw_id = cursor.lastrowid

                # Corrected 13 columns with 13 values matching exactly
                cursor.execute("""
                INSERT INTO cleaned_fare_quotes 
                (raw_quote_id, observed_at, source, origin, destination, departure_date, advance_days, airline, flight_number, cabin_class, base_fare, taxes_fees, total_fare)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (raw_id, now.isoformat(), source, o, d, flight_date, days, air_name, flight_no, "Economy", pure_base, taxes, fare))

    conn.commit()
    print(f"✅ Successfully initialized {DB_FILE} with 8 DGCA routes and populated {len(routes)*len(horizons)*len(airlines)} flight quotes.")

if __name__ == "__main__":
    conn = init_db()
    seed_data(conn)
    conn.close()