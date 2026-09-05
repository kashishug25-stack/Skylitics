"""
train_ml_engine.py — SKYLITICS / VimanSuchak ML Price Surge & Gouging Detection Engine
Reads cleaned_fare_quotes + route_basket from airfare_intelligence.db, trains an
unsupervised anomaly-detection model (Isolation Forest) per corridor+horizon,
and writes per-quote and per-corridor predictions to ml_predictions.json.

This is deliberately a companion to calculate_index.py, not a replacement for it:
calculate_index.py computes the official Laspeyres index using fixed thresholds
(>=135 Surge Spike, >=105 Moderate). This script adds a *statistical, adaptive*
layer on top — it learns what "normal" looks like per route/horizon instead of
using one global cutoff, and separately flags fares that look like unexplained
price gouging vs. expected demand-driven surge (weekend/last-minute/festival).

Usage:
    python train_ml_engine.py
Outputs:
    ml_predictions.json
"""

import sqlite3
import json
import datetime
import warnings

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error

warnings.filterwarnings("ignore")

DB_FILE = "airfare_intelligence.db"
OUTPUT_FILE = "ml_predictions.json"
ANOMALY_MODEL_FILE = "price_anomaly_model.pkl"
DECAY_MODEL_FILE = "price_decay_model.pkl"

# Standard advance-purchase horizons the decay curve is reported at, per the
# problem statement's T+1/T+7/T+15/T+30/T+45 basket.
DECAY_HORIZONS = [45, 30, 15, 7, 1]

# Minimum number of quotes needed in a corridor+horizon group before we trust
# a per-group model; below this we fall back to a global model so small routes
# still get predictions instead of being skipped.
MIN_GROUP_SIZE = 8

# Festival / peak-demand blackout dates (extend this list as needed). If a
# departure_date falls in one of these windows we treat elevated fares as
# expected "Surge" rather than unexplained "Gouging".
PEAK_WINDOWS = [
    ("2026-10-18", "2026-10-24"),  # Diwali corridor (example)
    ("2026-12-22", "2027-01-02"),  # New Year travel
]


def is_peak_date(date_str):
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return False
    for start, end in PEAK_WINDOWS:
        s = datetime.datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.datetime.strptime(end, "%Y-%m-%d").date()
        if s <= d <= e:
            return True
    return False


# Fallback route basket, used only if the route_basket table doesn't exist
# yet (e.g. a clean machine that ran the scraper but not seed_database.py).
FALLBACK_ROUTES = [
    ("DEL", "BOM", "Delhi - Mumbai", 6850000, 4600),
    ("DEL", "BLR", "Delhi - Bengaluru", 4920000, 5200),
    ("BOM", "BLR", "Mumbai - Bengaluru", 3890000, 3800),
    ("DEL", "CCU", "Delhi - Kolkata", 3450000, 4800),
    ("BLR", "HYD", "Bengaluru - Hyderabad", 2980000, 3100),
    ("MAA", "DEL", "Chennai - Delhi", 2840000, 5100),
    ("DEL", "GOI", "Delhi - Goa", 2650000, 4900),
    ("DEL", "PAT", "Delhi - Patna", 2220000, 4300),
]


def load_data(conn):
    quotes = pd.read_sql_query(
        """
        SELECT id, observed_at, source, origin, destination, departure_date,
               advance_days, airline, flight_number, cabin_class,
               base_fare, taxes_fees, total_fare
        FROM cleaned_fare_quotes
        WHERE cabin_class = 'Economy'
        """,
        conn,
    )
    try:
        routes = pd.read_sql_query(
            """
            SELECT origin, destination, route_name, route_weight, base_tariff_inr
            FROM route_basket WHERE is_active = 1
            """,
            conn,
        )
        if routes.empty:
            raise ValueError("route_basket table is empty")
    except Exception:
        total_pax = sum(r[3] for r in FALLBACK_ROUTES)
        routes = pd.DataFrame(
            [
                {
                    "origin": o, "destination": d, "route_name": name,
                    "route_weight": round(pax / total_pax, 4),
                    "base_tariff_inr": base,
                }
                for o, d, name, pax, base in FALLBACK_ROUTES
            ]
        )
    return quotes, routes


def engineer_features(quotes, routes):
    df = quotes.merge(routes, on=["origin", "destination"], how="inner")
    if df.empty:
        return df

    df["corridor"] = df["origin"] + "-" + df["destination"]
    df["price_ratio"] = df["total_fare"] / df["base_tariff_inr"]
    df["tax_ratio"] = df["taxes_fees"] / df["total_fare"].replace(0, np.nan)
    df["is_peak"] = df["departure_date"].apply(is_peak_date)

    try:
        dep = pd.to_datetime(df["departure_date"])
        df["day_of_week"] = dep.dt.dayofweek
        df["is_weekend_departure"] = df["day_of_week"].isin([4, 5, 6]).astype(int)
    except Exception:
        df["day_of_week"] = 0
        df["is_weekend_departure"] = 0

    airline_enc = LabelEncoder()
    df["airline_code"] = airline_enc.fit_transform(df["airline"])
    source_enc = LabelEncoder()
    df["source_code"] = source_enc.fit_transform(df["source"])

    grp = df.groupby(["corridor", "advance_days"])["total_fare"]
    df["group_median"] = grp.transform("median")
    df["group_std"] = grp.transform("std").replace(0, np.nan)
    df["group_size"] = grp.transform("size")
    df["z_score"] = ((df["total_fare"] - df["group_median"]) / df["group_std"]).fillna(0)

    mad = grp.transform(lambda s: (s - s.median()).abs().median()).replace(0, np.nan)
    df["robust_z_score"] = (0.6745 * (df["total_fare"] - df["group_median"]) / mad).fillna(0)

    return df


def train_and_score(df, return_models=False):
    feature_cols = [
        "price_ratio", "tax_ratio", "advance_days", "day_of_week",
        "is_weekend_departure", "airline_code", "source_code", "z_score",
    ]

    df["anomaly_score"] = 0.0
    df["is_anomaly"] = False

    # Tuned contamination to 0.04 (4%) to reduce false positives on normal flights
    global_model = IsolationForest(
        n_estimators=200, contamination=0.04, random_state=42
    )
    global_model.fit(df[feature_cols])
    global_scores = -global_model.score_samples(df[feature_cols])
    df["anomaly_score"] = global_scores
    df["is_anomaly"] = global_model.predict(df[feature_cols]) == -1

    group_models = {}

    for (corridor, days), group in df.groupby(["corridor", "advance_days"]):
        if len(group) < MIN_GROUP_SIZE:
            continue
        # Tuned per-group contamination to 0.05 (5%)
        model = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
        model.fit(group[feature_cols])
        scores = -model.score_samples(group[feature_cols])
        preds = model.predict(group[feature_cols]) == -1
        df.loc[group.index, "anomaly_score"] = scores
        df.loc[group.index, "is_anomaly"] = preds
        group_models[f"{corridor}|{days}"] = model

    lo, hi = df["anomaly_score"].min(), df["anomaly_score"].max()
    span = (hi - lo) if hi > lo else 1.0
    df["confidence"] = ((df["anomaly_score"] - lo) / span).round(3)

    # Tightened Z-Score override threshold to 3.5 to prevent flagging standard fluctuations
    Z_OVERRIDE_THRESHOLD = 3.5
    z_override = df["robust_z_score"].abs() > Z_OVERRIDE_THRESHOLD
    df["is_anomaly"] = df["is_anomaly"] | z_override
    df.loc[z_override, "confidence"] = df.loc[z_override, "confidence"].clip(lower=0.8)

    if return_models:
        return df, {"global": global_model, "groups": group_models, "feature_cols": feature_cols}
    return df


def train_price_decay_regressor(df):
    corridor_enc = LabelEncoder()
    df["corridor_code"] = corridor_enc.fit_transform(df["corridor"])

    feature_cols = [
        "advance_days", "day_of_week", "is_weekend_departure",
        "airline_code", "source_code", "corridor_code",
    ]
    X = df[feature_cols]
    y = df["total_fare"]

    if len(df) >= 20:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        eval_model = RandomForestRegressor(n_estimators=150, random_state=42)
        eval_model.fit(X_train, y_train)
        preds = eval_model.predict(X_test)
        metrics = {
            "r2": round(float(r2_score(y_test, preds)), 4),
            "mae_inr": round(float(mean_absolute_error(y_test, preds)), 2),
            "evaluated_on_n_holdout": int(len(y_test)),
        }
    else:
        metrics = {
            "r2": None, "mae_inr": None,
            "note": "Fewer than 20 quotes — not enough data for a reliable holdout split yet.",
        }

    model = RandomForestRegressor(n_estimators=150, random_state=42)
    model.fit(X, y)

    return model, metrics, corridor_enc, feature_cols


def build_decay_curves(df, model, corridor_enc, feature_cols):
    curves = {}
    for corridor in df["corridor"].unique():
        sub = df[df["corridor"] == corridor]
        mode_dow = int(sub["day_of_week"].mode().iloc[0])
        mode_airline = int(sub["airline_code"].mode().iloc[0])
        mode_source = int(sub["source_code"].mode().iloc[0])
        c_code = int(corridor_enc.transform([corridor])[0])
        is_weekend = 1 if mode_dow in [4, 5, 6] else 0

        curve = {}
        for h in DECAY_HORIZONS:
            row = pd.DataFrame([{
                "advance_days": h,
                "day_of_week": mode_dow,
                "is_weekend_departure": is_weekend,
                "airline_code": mode_airline,
                "source_code": mode_source,
                "corridor_code": c_code,
            }])[feature_cols]
            curve[str(h)] = round(float(model.predict(row)[0]), 2)
        curves[corridor] = curve
    return curves


def classify_surge_vs_gouging(row):
    if not row["is_anomaly"] or row["price_ratio"] <= 1.05:
        return "Normal"
    if row["is_peak"] or row["advance_days"] <= 1:
        return "Expected Surge"
    return "Potential Gouging"


def build_predictions_payload(df, decay_curves=None, decay_metrics=None):
    now = datetime.datetime.now().isoformat()

    quote_level = []
    for _, r in df.iterrows():
        quote_level.append({
            "id": int(r["id"]),
            "corridor": r["corridor"],
            "advance_days": int(r["advance_days"]),
            "airline": r["airline"],
            "cabin_class": r["cabin_class"],
            "total_fare": round(float(r["total_fare"]), 2),
            "price_ratio": round(float(r["price_ratio"]), 3),
            "z_score": round(float(r["z_score"]), 2),
            "anomaly_score": round(float(r["anomaly_score"]), 4),
            "confidence": float(r["confidence"]),
            "is_anomaly": bool(r["is_anomaly"]),
            "classification": r["ml_classification"],
        })

    corridor_level = {}
    for (corridor, days), group in df.groupby(["corridor", "advance_days"]):
        key = corridor
        corridor_level.setdefault(key, {})
        corridor_level[key][str(days)] = {
            "n_quotes": int(len(group)),
            "median_fare": round(float(group["total_fare"].median()), 2),
            "predicted_normal_fare": round(float(group["group_median"].iloc[0]), 2),
            "anomaly_rate": round(float(group["is_anomaly"].mean()), 3),
            "avg_confidence": round(float(group["confidence"].mean()), 3),
            "dominant_classification": group["ml_classification"].mode().iloc[0]
            if not group["ml_classification"].mode().empty else "Normal",
            "gouging_alerts": int((group["ml_classification"] == "Potential Gouging").sum()),
            "surge_alerts": int((group["ml_classification"] == "Expected Surge").sum()),
        }

    payload = {
        "generated_at": now,
        "model": "IsolationForest (per corridor+horizon, global fallback)",
        "n_quotes_scored": int(len(df)),
        "n_corridors": int(df["corridor"].nunique()),
        "summary": {
            "total_anomalies": int(df["is_anomaly"].sum()),
            "potential_gouging": int((df["ml_classification"] == "Potential Gouging").sum()),
            "expected_surge": int((df["ml_classification"] == "Expected Surge").sum()),
        },
        "corridors": corridor_level,
        "quotes": quote_level,
        "price_decay_model": {
            "type": "RandomForestRegressor",
            "predicts": "total_fare from advance_days + corridor + context",
            "accuracy": decay_metrics or {},
            "decay_curves": decay_curves or {},
        },
    }
    return payload


def main():
    conn = sqlite3.connect(DB_FILE)
    quotes, routes = load_data(conn)
    conn.close()

    if quotes.empty or routes.empty:
        print("[!] No data found — run seed_database.py / scraper.py first.")
        return

    df = engineer_features(quotes, routes)
    if df.empty:
        print("[!] No quotes matched an active route in route_basket.")
        return

    df, anomaly_models = train_and_score(df, return_models=True)
    df["ml_classification"] = df.apply(classify_surge_vs_gouging, axis=1)

    decay_model, decay_metrics, corridor_enc, decay_feature_cols = train_price_decay_regressor(df)
    decay_curves = build_decay_curves(df, decay_model, corridor_enc, decay_feature_cols)

    payload = build_predictions_payload(df, decay_curves, decay_metrics)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(payload, f, indent=2)

    joblib.dump(anomaly_models, ANOMALY_MODEL_FILE)
    joblib.dump(
        {"model": decay_model, "corridor_encoder": corridor_enc, "feature_cols": decay_feature_cols},
        DECAY_MODEL_FILE,
    )

    print("=" * 60)
    print("SKYLITICS ML SURGE & GOUGING DETECTION ENGINE")
    print("=" * 60)
    print(f"Quotes scored:        {payload['n_quotes_scored']}")
    print(f"Corridors covered:    {payload['n_corridors']}")
    print(f"Total anomalies:      {payload['summary']['total_anomalies']}")
    print(f"Potential gouging:    {payload['summary']['potential_gouging']}")
    print(f"Expected surge:       {payload['summary']['expected_surge']}")
    print("-" * 60)
    print(f"Price decay model R2:  {decay_metrics.get('r2')}")
    print(f"Price decay model MAE: Rs {decay_metrics.get('mae_inr')}")
    print("-" * 60)
    print(f"Output written to:    {OUTPUT_FILE}")
    print(f"Anomaly models saved: {ANOMALY_MODEL_FILE}")
    print(f"Decay model saved:    {DECAY_MODEL_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()