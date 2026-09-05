import os
import sqlite3
import json
import csv
import io
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Query, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import scraper
import calculate_index

app = FastAPI(
    title="Skylitics - DGCA & MoSPI Airfare Intelligence API",
    version="4.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "airfare_intelligence.db")
JSON_PATH = str(BASE_DIR / "dashboard_data.json")

CORRIDORS_8 = {
    "DEL-BOM": 0.2299,
    "DEL-BLR": 0.1651,
    "BOM-BLR": 0.1305,
    "DEL-CCU": 0.1158,
    "BLR-HYD": 0.1000,
    "MAA-DEL": 0.0953,
    "DEL-GOI": 0.0889,
    "DEL-PAT": 0.0745
}

SCRAPE_IN_PROGRESS = False
scheduler = AsyncIOScheduler()

async def run_full_pipeline_task():
    global SCRAPE_IN_PROGRESS
    SCRAPE_IN_PROGRESS = True
    print(f"\n[🔄 {datetime.now().strftime('%H:%M:%S')}] APScheduler: Starting scheduled data refresh...")
    try:
        if hasattr(scraper, "main"):
            if asyncio.iscoroutinefunction(scraper.main):
                await scraper.main()
            else:
                scraper.main()

        if hasattr(calculate_index, "run_laspeyres_engine"):
            calculate_index.run_laspeyres_engine()
        elif hasattr(calculate_index, "main"):
            calculate_index.main()

        print(f"[✔ {datetime.now().strftime('%H:%M:%S')}] APScheduler: Background sync complete! Fresh data ready.\n")
    except Exception as e:
        print(f"[-] APScheduler error: {e}")
    finally:
        SCRAPE_IN_PROGRESS = False

@app.on_event("startup")
async def start_background_daemon():
    scheduler.add_job(run_full_pipeline_task, "interval", hours=4, id="auto_airfare_refresh")
    scheduler.start()

@app.on_event("shutdown")
def stop_background_daemon():
    scheduler.shutdown()

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def load_json_data():
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

@app.get("/")
def serve_index():
    index_file = BASE_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "index.html not found"}

@app.post("/api/trigger-refresh")
async def manual_trigger_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_full_pipeline_task)
    return {"status": "success", "message": "Scraping & Laspeyres engine started."}

@app.get("/api/sync-status")
def get_sync_status(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    conn = get_db()
    latest_row = conn.execute("""
        SELECT datetime(MAX(observed_at), '+5 hours', '+30 minutes') AS latest_time, 
               COUNT(*) as total_records 
        FROM cleaned_fare_quotes
    """).fetchone()
    conn.close()
    
    return {
        "in_progress": SCRAPE_IN_PROGRESS,
        "latest_update": latest_row["latest_time"] if latest_row and latest_row["latest_time"] else "Active",
        "total_records": latest_row["total_records"] if latest_row else 0
    }

@app.get("/api/heatmap")
def get_sector_heatmap(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    conn = get_db()
    rows = conn.execute("""
        SELECT origin, destination, CAST(advance_days AS INTEGER) AS advance_days, 
               AVG(CAST(total_fare AS REAL)) AS avg_fare, 
               COUNT(*) AS total_quotes
        FROM cleaned_fare_quotes
        WHERE cabin_class = 'Economy'
          AND airline != 'Scheduled Airline'
        GROUP BY origin, destination, CAST(advance_days AS INTEGER)
    """).fetchall()
    conn.close()

    grouped = {}
    for r in rows:
        c = f"{r['origin']}-{r['destination']}"
        if c not in grouped:
            grouped[c] = {"origin": r["origin"], "destination": r["destination"], "horizons": {}}
        grouped[c]["horizons"][r["advance_days"]] = float(r["avg_fare"])

    heatmap_list = []
    for corridor, weight in CORRIDORS_8.items():
        orig, dest = corridor.split("-")
        h = grouped.get(corridor, {}).get("horizons", {})
        
        base_fare = h.get(30) or h.get(45) or h.get(15) or h.get(7, 5400.0)
        if not base_fare or base_fare < 2000:
            base_fare = 5400.0

        f1 = h.get(1, base_fare * 1.30)
        f7 = h.get(7, base_fare * 1.05)
        f15 = h.get(15, base_fare * 0.96)
        f30 = h.get(30, base_fare)
        f45 = h.get(45, base_fare * 0.90)

        p7_rel = round((f7 / base_fare) * 100, 1)
        surge_status = "High" if p7_rel >= 130 else ("Moderate" if p7_rel >= 105 else "Optimal")

        heatmap_list.append({
            "corridor": corridor,
            "origin": orig,
            "destination": dest,
            "weight": weight,
            "surge_status": surge_status,
            "surge_1d": f"₹{int(f1):,}",
            "standard_7d": f"₹{int(f7):,}",
            "surge_15d": f"₹{int(f15):,}",
            "surge_30d": f"₹{int(f30):,}",
            "surge_45d": f"₹{int(f45):,}",
            "base_fare": int(base_fare)
        })

    heatmap_list.sort(key=lambda x: x["weight"], reverse=True)
    return heatmap_list

@app.get("/api/index")
def get_index_metrics(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    data = load_json_data()
    return {
        "composite_index": data.get("national_composite_index", 115.78),
        "monthly_change": data.get("monthly_change", 15.78),
        "yearly_change": data.get("yearly_change", 10.25),
        "macro_validation_score": data.get("macro_validation_score", 0.92)
    }

@app.get("/api/flights")
def get_flight_quotes(
    response: Response,
    origin: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    advance_days: Optional[int] = Query(7),
    cabin_class: Optional[str] = Query("Economy")
):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    clean_orig = origin.split()[0].strip().upper() if origin else "DEL"
    clean_dest = destination.split()[0].strip().upper() if destination else "BOM"
    target_cabin = "Economy"
    if "business" in (cabin_class or "").lower():
        target_cabin = "Business"
    elif "premium" in (cabin_class or "").lower():
        target_cabin = "Premium Economy"
    elif "first" in (cabin_class or "").lower():
        target_cabin = "First Class"

    conn = get_db()

    # Find latest date scraped for this corridor and advance window to avoid old stale runs
    latest_date_row = conn.execute("""
        SELECT MAX(departure_date) as max_dep_date 
        FROM cleaned_fare_quotes
        WHERE origin = ? AND destination = ? AND CAST(advance_days AS INTEGER) = ?
    """, (clean_orig, clean_dest, advance_days)).fetchone()
    
    max_dep_date = latest_date_row["max_dep_date"] if latest_date_row and latest_date_row["max_dep_date"] else None

    # Matches Google Flights sorting: Lowest fare first, then chronological departure time
    query = """
        SELECT origin, destination, departure_date, departure_time, arrival_time, duration, advance_days, 
               airline, flight_number, cabin_class, stops, emissions, 
               COALESCE(flight_category, 'Other Flights') AS flight_category,
               CAST(base_fare AS REAL) as base_fare, 
               CAST(taxes_fees AS REAL) as taxes_fees, 
               MIN(CAST(total_fare AS REAL)) as total_fare
        FROM cleaned_fare_quotes
        WHERE origin = ? AND destination = ? AND CAST(advance_days AS INTEGER) = ? 
          AND LOWER(cabin_class) = LOWER(?)
          AND (? IS NULL OR departure_date = ?)
          AND airline != 'Scheduled Airline'
        GROUP BY departure_time, arrival_time, airline
        ORDER BY 
          CASE WHEN flight_category LIKE '%Best%' THEN 0 ELSE 1 END,
          total_fare ASC,
          CASE 
            WHEN departure_time LIKE '%PM%' AND departure_time NOT LIKE '12:%' THEN 1200 + CAST(substr(departure_time, 1, instr(departure_time, ':') - 1) AS INTEGER) * 60 + CAST(substr(departure_time, instr(departure_time, ':') + 1, 2) AS INTEGER)
            WHEN departure_time LIKE '%AM%' AND departure_time LIKE '12:%' THEN CAST(substr(departure_time, instr(departure_time, ':') + 1, 2) AS INTEGER)
            ELSE CAST(substr(departure_time, 1, instr(departure_time, ':') - 1) AS INTEGER) * 60 + CAST(substr(departure_time, instr(departure_time, ':') + 1, 2) AS INTEGER)
          END ASC
    """
    rows = conn.execute(query, (clean_orig, clean_dest, advance_days, target_cabin, max_dep_date, max_dep_date)).fetchall()

    if not rows:
        fallback_query = """
            SELECT origin, destination, departure_date, departure_time, arrival_time, duration, advance_days, 
                   airline, flight_number, cabin_class, stops, emissions, 
                   COALESCE(flight_category, 'Other Flights') AS flight_category,
                   CAST(base_fare AS REAL) as base_fare, 
                   CAST(taxes_fees AS REAL) as taxes_fees, 
                   MIN(CAST(total_fare AS REAL)) as total_fare
            FROM cleaned_fare_quotes
            WHERE origin = ? AND destination = ? AND LOWER(cabin_class) = LOWER(?)
              AND airline != 'Scheduled Airline'
            GROUP BY departure_time, arrival_time, airline
            ORDER BY 
              CASE WHEN flight_category LIKE '%Best%' THEN 0 ELSE 1 END,
              total_fare ASC
        """
        rows = conn.execute(fallback_query, (clean_orig, clean_dest, target_cabin)).fetchall()

    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/export-mospi-csv")
def export_mospi_csv(
    origin: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    advance_days: Optional[int] = Query(None)
):
    clean_orig = origin.split()[0].strip().upper() if origin else None
    clean_dest = destination.split()[0].strip().upper() if destination else None

    conn = get_db()
    if clean_orig and clean_dest:
        rows = conn.execute("""
            SELECT origin, destination, departure_date, departure_time, arrival_time, duration, advance_days, airline, flight_number, cabin_class, stops, base_fare, taxes_fees, total_fare
            FROM cleaned_fare_quotes
            WHERE origin = ? AND destination = ? AND (? IS NULL OR CAST(advance_days AS INTEGER) = ?)
              AND airline != 'Scheduled Airline'
            GROUP BY departure_time, arrival_time, airline
            ORDER BY total_fare ASC
        """, (clean_orig, clean_dest, advance_days, advance_days)).fetchall()
        filename = f"Flight_Quotes_{clean_orig}_{clean_dest}.csv"
    else:
        rows = conn.execute("""
            SELECT origin, destination, departure_date, departure_time, arrival_time, duration, advance_days, airline, flight_number, cabin_class, stops, base_fare, taxes_fees, total_fare
            FROM cleaned_fare_quotes
            WHERE airline != 'Scheduled Airline'
            GROUP BY origin, destination, departure_time, airline, advance_days
            ORDER BY origin, destination, advance_days
        """).fetchall()
        filename = f"MoSPI_AFI_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Airline", "Flight_Number", "Origin", "Destination", "Corridor",
        "Departure_Date", "Departure_Time", "Arrival_Time", "Duration", "Cabin_Class",
        "Stops", "Base_Fare_INR", "Taxes_Fees_INR", "Total_Fare_INR", "Advance_Days_Horizon", "DGCA_Weight"
    ])

    for r in rows:
        corridor = f"{r['origin']}-{r['destination']}"
        weight = CORRIDORS_8.get(corridor, 0.10)
        writer.writerow([
            r["airline"], r["flight_number"], r["origin"], r["destination"], corridor,
            r["departure_date"], r["departure_time"], r["arrival_time"], r["duration"], r["cabin_class"],
            r["stops"], r["base_fare"], r["taxes_fees"], r["total_fare"], r["advance_days"], weight
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

app.mount("/", StaticFiles(directory=str(BASE_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)