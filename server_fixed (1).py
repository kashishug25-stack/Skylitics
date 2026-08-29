"""
server_fixed.py — corrected version of server.py

WHAT CHANGED, AND WHY:
The original /index endpoint did this:
    "current_index": data.get("current_index", 114.6)
If dashboard_data.json was missing or incomplete, it silently returned
114.6 (and other fake numbers) as if they were real, computed results.
Anyone calling the API - including a judge - would have no way to tell
a fabricated placeholder from an actual calculation.

This version returns an explicit "data_available": false response
instead, whenever the real computed data isn't there yet. It never
invents a plausible-looking number.
"""

import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SKYLITICS Airfare API", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_data():
    try:
        with open("dashboard_data.json", "r") as f:
            return json.load(f), True
    except Exception:
        return {}, False


@app.get("/")
def home():
    return {"message": "SKYLITICS MoSPI Airfare API is running"}


@app.get("/index")
def get_index():
    data, file_found = load_data()

    required_fields = ["current_index", "monthly_change", "yearly_change"]
    have_all_fields = file_found and all(f in data for f in required_fields)

    if not have_all_fields:
        # Explicit, honest response - no fabricated numbers.
        return {
            "data_available": False,
            "message": "Index has not been computed yet. Run calculate_index.py after collecting real fare data.",
        }

    return {
        "data_available": True,
        "current_index": data["current_index"],
        "monthly_change": data["monthly_change"],
        "yearly_change": data["yearly_change"],
    }


@app.get("/routes")
def get_routes():
    data, file_found = load_data()
    routes = data.get("routes", []) if file_found else []
    return {"data_available": bool(routes), "routes": routes}


@app.get("/flights")
def get_flights():
    data, file_found = load_data()
    flights = data.get("raw_flights", []) if file_found else []
    return {"data_available": bool(flights), "flights": flights}


@app.get("/analytics")
def get_analytics():
    data, file_found = load_data()
    if not file_found or "avg_fare" not in data:
        return {"data_available": False, "message": "Analytics not yet computed."}
    return {
        "data_available": True,
        "avg_fare": data.get("avg_fare"),
        "total_quotes": data.get("total_quotes"),
        "horizon_fares": data.get("horizon_fares"),
    }


@app.get("/health")
def health_check():
    """New endpoint - useful for judges/dashboard to confirm the API and
    data pipeline are actually alive, separate from whether data exists yet."""
    _, file_found = load_data()
    return {"api_status": "running", "data_file_found": file_found}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
