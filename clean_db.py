import sqlite3

conn = sqlite3.connect("airfare_intelligence.db")
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS cleaned_fare_quotes")
cur.execute("""
    CREATE TABLE cleaned_fare_quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        departure_date TEXT NOT NULL,
        departure_time TEXT NOT NULL,
        arrival_time TEXT NOT NULL,
        duration TEXT NOT NULL,
        advance_days INTEGER NOT NULL,
        airline TEXT NOT NULL,
        flight_number TEXT NOT NULL,
        cabin_class TEXT DEFAULT 'Economy',
        stops TEXT DEFAULT 'Nonstop',
        emissions TEXT DEFAULT '89 kg CO2e',
        base_fare REAL NOT NULL,
        taxes_fees REAL NOT NULL,
        total_fare REAL NOT NULL,
        flight_category TEXT DEFAULT 'Best Flights',
        source TEXT DEFAULT 'Google Flights',
        observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(origin, destination, departure_date, departure_time, arrival_time, airline, total_fare)
    )
""")
conn.commit()
conn.close()
print("[✔] Database schema reset and ready.")