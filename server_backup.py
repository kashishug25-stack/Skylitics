"""
server.py — Skylitics FastAPI Policy & Analytics Backend
Exposes live endpoints for MoSPI, RBI, and frontend dashboard integration.
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import sqlite3
import datetime
from calculate_index import compute_airfare_index

app = FastAPI(
    title="Skylitics — National Airfare Price Index API",
    description="MoSPI CPI & DGCA compliant real-time airfare monitoring API engine.",
    version="2.0.0"
)

# Enable CORS for local and web browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "airfare_intelligence.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def root():
    return {
        "portal": "Skylitics National Airfare Price Index",
        "status": "Online",
        "standard": "MoSPI CPI Framework & Laspeyres Formula",
        "version": "2.0.0",
        "interactive_docs": "/docs",
        "endpoints": ["/api/index", "/api/routes", "/api/flights", "/api/heatmap", "/api/export-mospi-csv"]
    }

@app.get("/api/index")
def get_index():
    """Computes and returns real-time national composite and corridor Laspeyres indices."""
    return compute_airfare_index()

@app.get("/api/routes")
def get_routes():
    """Returns the official DGCA passenger-traffic weighted route basket."""
    conn = get_db()
    routes = conn.execute("SELECT origin, destination, route_name, annual_pax, route_weight, base_tariff_inr FROM route_basket WHERE is_active = 1").fetchall()
    conn.close()
    return [dict(r) for r in routes]

@app.get("/api/flights")
def get_flights(
    origin: str = Query(...),
    destination: str = Query(...),
    advance_days: int = Query(7)
):
    """Fetches verified scheduled carrier flight quotes with full tax/surcharge breakdowns."""
    conn = get_db()
    rows = conn.execute("""
        SELECT source, origin, destination, departure_date, advance_days, airline, flight_number, cabin_class, base_fare, taxes_fees, total_fare 
        FROM cleaned_fare_quotes
        WHERE origin = ? AND destination = ? AND advance_days = ?
    """, (origin, destination, advance_days)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/heatmap")
def get_heatmap():
    """Returns sector-wise price surge intensity for dashboard heatmap visualizations."""
    index_data = compute_airfare_index()
    heatmap_list = []
    for corridor, details in index_data["corridors"].items():
        p1 = details["horizons"].get(1, {}).get("price_relative", 100)
        p7 = details["horizons"].get(7, {}).get("price_relative", 100)
        heatmap_list.append({
            "corridor": corridor,
            "route_name": details["route_name"],
            "origin": details["origin"],
            "destination": details["destination"],
            "weight": details["weight"],
            "1d_surge_relative": p1,
            "7d_relative": p7,
            "surge_intensity": "High" if p1 >= 140 else ("Moderate" if p1 >= 110 else "Low")
        })
    return heatmap_list

@app.get("/api/export-mospi-csv")
def export_mospi_csv():
    """Generates and downloads a standardized MoSPI CPI compliance CSV report."""
    conn = get_db()
    rows = conn.execute("""
        SELECT c.observed_at, c.origin, c.destination, c.advance_days, c.airline, c.flight_number, c.base_fare, c.taxes_fees, c.total_fare, r.route_weight
        FROM cleaned_fare_quotes c
        JOIN route_basket r ON c.origin = r.origin AND c.destination = r.destination
        ORDER BY c.origin, c.destination, c.advance_days
    """).fetchall()
    conn.close()

    csv_output = "Timestamp,Corridor,AdvanceHorizon,Airline,FlightNumber,BaseFareINR,TaxesFeesINR,TotalTariffINR,DGCAWeight\n"
    for r in rows:
        corridor = f"{r['origin']}-{r['destination']}"
        csv_output += f"{r['observed_at']},{corridor},{r['advance_days']}d,{r['airline']},{r['flight_number']},{r['base_fare']},{r['taxes_fees']},{r['total_fare']},{r['route_weight']}\n"

    return Response(
        content=csv_output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Skylitics_MoSPI_Airfare_Report.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)