"""
phase1_sanitize.py — Safely backs up the database, eliminates 
'Scheduled Airline' placeholders, and removes extreme layovers (> 8 hours).
Preserves 100% of authentic domestic nonstops and reasonable 1-stop connections.
"""

import sqlite3
import shutil

DB_FILE = "airfare_intelligence.db"
BACKUP_FILE = "airfare_intelligence_backup.db"

# 1. Safety First: Create a full backup
shutil.copy(DB_FILE, BACKUP_FILE)
print(f"[✔] Safety backup created: '{BACKUP_FILE}'")

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

initial_count = cur.execute("SELECT COUNT(*) FROM cleaned_fare_quotes").fetchone()[0]

# 2. Delete 'Scheduled Airline' and non-direct overnight layovers (> 8 hours)
cur.execute("""
    DELETE FROM cleaned_fare_quotes
    WHERE airline = 'Scheduled Airline'
       OR (duration LIKE '%hr%' 
           AND CAST(substr(duration, 1, instr(duration, 'hr') - 1) AS INTEGER) > 8 
           AND stops != 'Nonstop')
""")

deleted_rows = cur.rowcount
conn.commit()

remaining_count = cur.execute("SELECT COUNT(*) FROM cleaned_fare_quotes").fetchone()[0]
print(f"[✔] Deleted {deleted_rows} corrupted/outlier quotes.")
print(f"[✔] Initial Rows: {initial_count} ➔ Remaining Genuine Rows: {remaining_count}")

# 3. Print verified summary across all airlines and cabin classes
summary = cur.execute("""
    SELECT cabin_class, airline, COUNT(*), ROUND(AVG(total_fare)), MIN(total_fare), MAX(total_fare)
    FROM cleaned_fare_quotes
    GROUP BY cabin_class, airline
    ORDER BY cabin_class, airline
""").fetchall()

print("\n" + "=" * 80)
print(f"{'CABIN CLASS':<18} | {'AIRLINE':<20} | {'QUOTES':<8} | {'AVG FARE':<12} | {'PRICE RANGE'}")
print("=" * 80)
for c, a, cnt, avg_f, min_f, max_f in summary:
    print(f"{c:<18} | {a:<20} | {cnt:<8} | ₹{int(avg_f):<10,} | ₹{int(min_f):,} - ₹{int(max_f):,}")
print("=" * 80)

conn.close()
print("\n[SUCCESS] Phase 1 Database Sanitization Complete!")