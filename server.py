import json
import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SKYLITICS Airfare API", version="1.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_data():
    try:
        with open("dashboard_data.json", "r") as f:
            return json.load(f)
    except Exception:
        return {}

@app.get("/")
def home():
    return {"message": "SKYLITICS MoSPI Airfare API is running"}

@app.get("/index")
def get_index():
    data = load_data()
    return {
        "current_index": data.get("current_index", 114.6),
        "monthly_change": data.get("monthly_change", 4.2),
        "yearly_change": data.get("yearly_change", 12.7)
    }

@app.get("/routes")
def get_routes():
    data = load_data()
    return data.get("routes", [])

@app.get("/flights")
def get_flights():
    data = load_data()
    return data.get("raw_flights", [])

@app.get("/analytics")
def get_analytics():
    data = load_data()
    return {
        "avg_fare": data.get("avg_fare"),
        "total_quotes": data.get("total_quotes"),
        "horizon_fares": data.get("horizon_fares")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)