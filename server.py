import os
import sqlite3
import json
import csv
import io
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Skylitics - DGCA & MoSPI Airfare Intelligence API",
    version="3.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "airfare_intelligence.db"
JSON_PATH = "dashboard_data.json"

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

def get_db():
    conn = sqlite3.connect(DB_PATH)
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
    if Path("index.html").exists():
        return FileResponse("index.html")
    return {"error": "index.html not found"}

@app.get("/api/heatmap")
def get_sector_heatmap():
    conn = get_db()
    rows = conn.execute("""
        SELECT origin, destination, CAST(advance_days AS INTEGER) AS advance_days, 
               AVG(CAST(total_fare AS REAL)) AS avg_fare, 
               COUNT(*) AS total_quotes
        FROM cleaned_fare_quotes
        WHERE CAST(total_fare AS REAL) BETWEEN 2500 AND 28000
        GROUP BY origin, destination, CAST(advance_days AS INTEGER)
    """).fetchall()
    conn.close()

    grouped = {}
    for r in rows:
        c = f"{r['origin']}-{r['destination']}"
        if c not in grouped:
            grouped[c] = {"origin": r["origin"], "destination": r["destination"], "horizons": {}}
        grouped[c]["horizons"][r["advance_days"]] = {
            "avg_fare": float(r["avg_fare"]),
            "count": int(r["total_quotes"])
        }

    heatmap_list = []
    for corridor, weight in CORRIDORS_8.items():
        orig, dest = corridor.split("-")
        h = grouped.get(corridor, {}).get("horizons", {})
        
        base_fare = (
            h.get(30, {}).get("avg_fare") or 
            h.get(45, {}).get("avg_fare") or 
            h.get(15, {}).get("avg_fare") or 
            h.get(7, {}).get("avg_fare", 5400.0)
        )
        if not base_fare or base_fare < 2500 or base_fare > 28000:
            base_fare = 5400.0

        f1 = h.get(1, {}).get("avg_fare", base_fare * 1.35)
        f7 = h.get(7, {}).get("avg_fare", base_fare * 1.08)
        f15 = h.get(15, {}).get("avg_fare", base_fare * 0.96)
        f30 = h.get(30, {}).get("avg_fare", base_fare)
        f45 = h.get(45, {}).get("avg_fare", base_fare * 0.90)

        p7_rel = round((f7 / base_fare) * 100, 1)
        surge_status = "High" if p7_rel >= 135 else ("Moderate" if p7_rel >= 110 else "Optimal")

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
            "surge_1d_raw": int(f1),
            "standard_7d_raw": int(f7),
            "surge_15d_raw": int(f15),
            "surge_30d_raw": int(f30),
            "surge_45d_raw": int(f45),
            "base_fare": int(base_fare)
        })

    heatmap_list.sort(key=lambda x: x["weight"], reverse=True)
    return heatmap_list

@app.get("/api/index")
def get_index_metrics():
    data = load_json_data()
    return {
        "composite_index": data.get("national_composite_index", 108.4),
        "monthly_change": data.get("monthly_change", 8.4),
        "yearly_change": data.get("yearly_change", 5.5),
        "macro_validation_score": data.get("macro_validation_score", 0.94)
    }

@app.get("/api/flights")
def get_flight_quotes(
    origin: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    advance_days: Optional[int] = Query(7),
    cabin_class: Optional[str] = Query("Economy")
):
    clean_orig = origin.split()[0].strip().upper() if origin else "DEL"
    clean_dest = destination.split()[0].strip().upper() if destination else "BOM"
    raw_cabin = (cabin_class or "Economy").strip()

    if "business" in raw_cabin.lower():
        target_cabin = "Business"
    elif "premium" in raw_cabin.lower():
        target_cabin = "Premium Economy"
    elif "first" in raw_cabin.lower():
        target_cabin = "First Class"
    else:
        target_cabin = "Economy"

    conn = get_db()
    rows = conn.execute("""
        SELECT origin, destination, departure_date, departure_time, arrival_time, duration, advance_days, 
               airline, flight_number, cabin_class, stops, emissions, flight_category,
               CAST(base_fare AS REAL) as base_fare, 
               CAST(taxes_fees AS REAL) as taxes_fees, 
               CAST(total_fare AS REAL) as total_fare
        FROM cleaned_fare_quotes
        WHERE origin = ? AND destination = ? AND CAST(advance_days AS INTEGER) = ? AND cabin_class = ?
        ORDER BY CASE WHEN flight_category = 'Best Flights' THEN 0 ELSE 1 END, total_fare ASC
    """, (clean_orig, clean_dest, advance_days, target_cabin)).fetchall()

    if not rows:
        rows = conn.execute("""
            SELECT origin, destination, departure_date, departure_time, arrival_time, duration, advance_days, 
                   airline, flight_number, cabin_class, stops, emissions, flight_category,
                   CAST(base_fare AS REAL) as base_fare, 
                   CAST(taxes_fees AS REAL) as taxes_fees, 
                   CAST(total_fare AS REAL) as total_fare
            FROM cleaned_fare_quotes
            WHERE origin = ? AND destination = ? AND cabin_class = ?
            ORDER BY CASE WHEN flight_category = 'Best Flights' THEN 0 ELSE 1 END, total_fare ASC
        """, (clean_orig, clean_dest, target_cabin)).fetchall()

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
            ORDER BY total_fare ASC
        """, (clean_orig, clean_dest, advance_days, advance_days)).fetchall()
        filename = f"Flight_Quotes_{clean_orig}_{clean_dest}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    else:
        rows = conn.execute("""
            SELECT origin, destination, departure_date, departure_time, arrival_time, duration, advance_days, airline, flight_number, cabin_class, stops, base_fare, taxes_fees, total_fare
            FROM cleaned_fare_quotes
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

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)