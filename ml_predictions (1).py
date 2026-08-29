"""
ml_predictions.py — price forecasting + anomaly detection for Skylitics

Install first:
    pip install scikit-learn pandas numpy --break-system-packages

WHAT THIS DOES:
1. Loads real cleaned fare data (from cleaned_fare_quotes, produced by
   clean_data.py) plus optional historical Kaggle data for extra training
   signal.
2. Trains a simple, explainable prediction model (Random Forest - accurate
   but you can still inspect which features mattered, unlike a black-box
   deep learning model).
3. Detects anomalies using a statistical z-score method (how many standard
   deviations a price is from the route's normal range) - not a black box,
   easy to explain to judges.
4. Writes results into dashboard_data.json under "predictions" and
   "anomalies" keys, so the existing dashboard can pick them up.

DESIGN RULE (same one used in the scraper/API fixes):
If there isn't enough real data to make a trustworthy prediction, this
code says so explicitly - it never fabricates a plausible-looking number.
A hackathon judge respects "insufficient data yet" far more than a wrong
confident number.
"""

import json
import sqlite3
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

DB_FILE = "airfare_intelligence.db"
DASHBOARD_JSON = "dashboard_data.json"
HISTORICAL_CSV = "data/historical/historical_fares.csv"  # optional, from Kaggle

MIN_ROWS_TO_TRAIN = 30       # below this, we don't trust a trained model at all
MIN_ROWS_PER_ROUTE_ANOMALY = 5  # below this, we don't flag anomalies for that route


# ---------------------------------------------------------------------------
# 1. LOAD DATA
# ---------------------------------------------------------------------------

def load_cleaned_data() -> pd.DataFrame:
    """Loads real, cleaned, scraped fare data from SQLite."""
    if not Path(DB_FILE).exists():
        print(f"[WARN] Database '{DB_FILE}' not found yet.")
        return pd.DataFrame()

    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("""
            SELECT observed_at, origin, destination, departure_date,
                   advance_days, airline, total_fare, is_outlier
            FROM cleaned_fare_quotes
        """, conn)
    except Exception as e:
        print(f"[WARN] Could not read cleaned_fare_quotes: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()

    # Drop rows flagged as outliers when training the prediction model -
    # keep them only for anomaly detection reference, not for teaching the
    # model what a "normal" price looks like.
    return df


def load_historical_data() -> pd.DataFrame:
    """Loads optional Kaggle historical data, clearly separated from live data."""
    if not Path(HISTORICAL_CSV).exists():
        return pd.DataFrame()

    try:
        hist = pd.read_csv(HISTORICAL_CSV)
        print(f"Loaded {len(hist)} historical reference rows (for training only, "
              f"never presented as live data).")
        return hist
    except Exception as e:
        print(f"[WARN] Could not load historical data: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 2. PREDICTION MODEL
# ---------------------------------------------------------------------------

class FarePredictor:
    def __init__(self):
        self.model = None
        self.origin_encoder = LabelEncoder()
        self.dest_encoder = LabelEncoder()
        self.airline_encoder = LabelEncoder()
        self.is_trained = False
        self.training_row_count = 0

    def _build_features(self, df: pd.DataFrame, fit_encoders: bool) -> pd.DataFrame:
        df = df.copy()
        df["departure_date"] = pd.to_datetime(df["departure_date"], errors="coerce")
        df["day_of_week"] = df["departure_date"].dt.dayofweek.fillna(0).astype(int)

        if fit_encoders:
            df["origin_enc"] = self.origin_encoder.fit_transform(df["origin"].astype(str))
            df["dest_enc"] = self.dest_encoder.fit_transform(df["destination"].astype(str))
            df["airline_enc"] = self.airline_encoder.fit_transform(df["airline"].astype(str))
        else:
            # Handle values not seen during training gracefully instead of crashing
            df["origin_enc"] = df["origin"].astype(str).map(
                lambda v: self._safe_encode(self.origin_encoder, v))
            df["dest_enc"] = df["destination"].astype(str).map(
                lambda v: self._safe_encode(self.dest_encoder, v))
            df["airline_enc"] = df["airline"].astype(str).map(
                lambda v: self._safe_encode(self.airline_encoder, v))

        return df[["advance_days", "day_of_week", "origin_enc", "dest_enc", "airline_enc"]]

    @staticmethod
    def _safe_encode(encoder: LabelEncoder, value: str) -> int:
        if value in encoder.classes_:
            return int(encoder.transform([value])[0])
        return -1  # unseen category - model will treat it as "unknown"

    def train(self, df: pd.DataFrame):
        # Only train on rows that aren't flagged as outliers, and only
        # if we genuinely have enough data to trust the result.
        clean = df[df.get("is_outlier", 0) == 0].dropna(subset=["total_fare"])
        self.training_row_count = len(clean)

        if self.training_row_count < MIN_ROWS_TO_TRAIN:
            print(f"[INFO] Only {self.training_row_count} usable rows - need at least "
                  f"{MIN_ROWS_TO_TRAIN} to train a trustworthy model. Skipping training.")
            self.is_trained = False
            return

        X = self._build_features(clean, fit_encoders=True)
        y = clean["total_fare"].values

        self.model = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
        self.model.fit(X, y)
        self.is_trained = True
        print(f"[OK] Model trained on {self.training_row_count} real fare observations.")

    def predict(self, origin, destination, advance_days, airline):
        if not self.is_trained:
            return {
                "prediction_available": False,
                "reason": f"Not enough training data yet (need {MIN_ROWS_TO_TRAIN}+ real "
                          f"observations, have {self.training_row_count})."
            }

        row = pd.DataFrame([{
            "origin": origin, "destination": destination,
            "departure_date": datetime.now(), "advance_days": advance_days,
            "airline": airline,
        }])
        X = self._build_features(row, fit_encoders=False)

        # A prediction from all individual trees gives us a range, not just
        # one number - this is what lets us say "likely between X and Y"
        # honestly, instead of a falsely precise single figure.
        tree_predictions = np.array([tree.predict(X)[0] for tree in self.model.estimators_])
        point_estimate = float(np.median(tree_predictions))
        low = float(np.percentile(tree_predictions, 10))
        high = float(np.percentile(tree_predictions, 90))

        return {
            "prediction_available": True,
            "predicted_fare": round(point_estimate, 2),
            "likely_range_low": round(low, 2),
            "likely_range_high": round(high, 2),
            "note": "Estimate based on historical + early live observations. "
                    "Not guaranteed - treat as a directional signal, not a quote.",
        }


# ---------------------------------------------------------------------------
# 3. ANOMALY DETECTION (statistical, explainable - not a black box)
# ---------------------------------------------------------------------------

def detect_anomalies(df: pd.DataFrame) -> list:
    """For each route + booking window, flags a fare as unusual if it's
    more than 2 standard deviations from that route's own normal range.
    Returns an empty, honest list if there isn't enough data - never guesses."""
    anomalies = []

    if df.empty:
        return anomalies

    grouped = df.groupby(["origin", "destination", "advance_days"])

    for (origin, dest, advance_days), group in grouped:
        if len(group) < MIN_ROWS_PER_ROUTE_ANOMALY:
            continue  # not enough history for this specific route/window to judge "normal"

        mean_fare = group["total_fare"].mean()
        std_fare = group["total_fare"].std()

        if std_fare == 0 or pd.isna(std_fare):
            continue  # no variation to measure against - skip rather than force a result

        latest = group.sort_values("observed_at").iloc[-1]
        z_score = (latest["total_fare"] - mean_fare) / std_fare

        if abs(z_score) >= 2:
            severity = "Highly Unusual" if abs(z_score) >= 3 else "Unusual"
            anomalies.append({
                "route": f"{origin}-{dest}",
                "advance_days": int(advance_days),
                "current_fare": float(latest["total_fare"]),
                "normal_average": round(float(mean_fare), 2),
                "z_score": round(float(z_score), 2),
                "severity": severity,
                "direction": "higher than normal" if z_score > 0 else "lower than normal",
            })

    return anomalies


# ---------------------------------------------------------------------------
# 4. SAVE RESULTS FOR THE DASHBOARD / API
# ---------------------------------------------------------------------------

def update_dashboard_json(predictions_summary: dict, anomalies: list):
    existing = {}
    if Path(DASHBOARD_JSON).exists():
        try:
            with open(DASHBOARD_JSON, "r") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    existing["predictions"] = predictions_summary
    existing["anomalies"] = anomalies
    existing["ml_last_updated"] = datetime.now().isoformat()

    with open(DASHBOARD_JSON, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"[OK] Wrote predictions + {len(anomalies)} anomalies to {DASHBOARD_JSON}")


# ---------------------------------------------------------------------------
# 5. MAIN
# ---------------------------------------------------------------------------

def run_ml_pipeline(sample_routes=None):
    live_data = load_cleaned_data()
    historical_data = load_historical_data()

    combined = pd.concat([live_data, historical_data], ignore_index=True) if not historical_data.empty else live_data

    if combined.empty:
        print("[WARN] No data at all yet - run the scraper and clean_data.py first.")
        update_dashboard_json({"prediction_available": False, "reason": "No data collected yet."}, [])
        return

    predictor = FarePredictor()
    predictor.train(combined)

    # Example predictions for your locked route basket - adjust as needed
    if sample_routes is None:
        sample_routes = [
            ("DEL", "BOM", 7, "IndiGo"),
            ("DEL", "BLR", 7, "IndiGo"),
            ("BOM", "BLR", 15, "Air India"),
        ]

    predictions = {}
    for origin, dest, days, airline in sample_routes:
        key = f"{origin}-{dest}_T{days}"
        predictions[key] = predictor.predict(origin, dest, days, airline)

    anomalies = detect_anomalies(live_data)  # anomaly detection uses REAL live data only,
                                              # not historical, since it's about "right now"

    update_dashboard_json(predictions, anomalies)

    print("\n" + "=" * 50)
    print("ML PIPELINE SUMMARY")
    print("=" * 50)
    for key, result in predictions.items():
        print(f"{key}: {result}")
    print(f"\nAnomalies detected: {len(anomalies)}")
    for a in anomalies:
        print(f"  {a['route']} T+{a['advance_days']}: {a['severity']} "
              f"(₹{a['current_fare']} vs normal ₹{a['normal_average']})")


if __name__ == "__main__":
    run_ml_pipeline()
