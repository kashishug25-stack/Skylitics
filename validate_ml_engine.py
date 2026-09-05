"""
validate_ml_engine.py — Backtest / validation harness for train_ml_engine.py

Why this exists:
train_ml_engine.py is unsupervised (Isolation Forest) — there's no ground-truth
"this fare was really gouging" label in real scraped data to measure accuracy
against. So this script creates a controlled test: it takes your real seeded
quotes as known-normal, injects synthetic fares with a KNOWN label (either
deliberate price gouging or a legitimate demand surge), runs them through the
exact same pipeline as train_ml_engine.py, and reports whether the model
actually caught them.

This is what you show a judge who asks "how do you know this model works?"

Usage:
    python validate_ml_engine.py
Outputs:
    backtest_report.json
    Console summary with recall / false-positive rate
"""

import sqlite3
import json
import random
import datetime

import numpy as np
import pandas as pd

# Reuse the exact same pipeline the real engine uses, so the backtest is
# testing the real code path, not a re-implementation of it.
from train_ml_engine import (
    load_data,
    engineer_features,
    train_and_score,
    classify_surge_vs_gouging,
    PEAK_WINDOWS,
)

DB_FILE = "airfare_intelligence.db"
REPORT_FILE = "backtest_report.json"

random.seed(42)
np.random.seed(42)

N_GOUGING_CASES = 25   # unexplained price spikes, non-peak, not last-minute
N_SURGE_CASES = 25     # spikes that ARE explained (peak dates or T+1)
N_NORMAL_SAMPLE = 60   # untouched real rows used to measure false positives


def inject_gouging_cases(base_rows, n):
    """Take real quotes and inflate fares 1.8x-3x on ordinary (non-peak,
    advance_days > 1) dates — this has no legitimate demand justification,
    so a correct model should flag these."""
    injected = []
    candidates = base_rows[base_rows["advance_days"] > 1].sample(
        n=min(n, len(base_rows[base_rows["advance_days"] > 1])), random_state=1
    )
    for i, row in candidates.reset_index(drop=True).iterrows():
        r = row.copy()
        factor = random.uniform(1.8, 3.0)
        r["id"] = -1000 - i
        r["total_fare"] = round(row["total_fare"] * factor, 2)
        r["taxes_fees"] = round(r["total_fare"] * 0.22, 2)
        r["base_fare"] = round(r["total_fare"] - r["taxes_fees"], 2)
        r["source"] = "SYNTHETIC_TEST"
        r["true_label"] = "Gouging"
        injected.append(r)
    return pd.DataFrame(injected)


def inject_surge_cases(base_rows, n):
    """Same inflation, but on dates that ARE justified: inside a peak window
    or at T+1 (last-minute). A correct model should still flag these as
    anomalous, but classify_surge_vs_gouging should label them 'Expected
    Surge' rather than 'Potential Gouging'."""
    injected = []
    peak_start = datetime.datetime.strptime(PEAK_WINDOWS[0][0], "%Y-%m-%d").date()
    candidates = base_rows.sample(n=min(n, len(base_rows)), random_state=2)
    for i, row in candidates.reset_index(drop=True).iterrows():
        r = row.copy()
        factor = random.uniform(1.8, 3.0)
        r["id"] = -2000 - i
        r["total_fare"] = round(row["total_fare"] * factor, 2)
        r["taxes_fees"] = round(r["total_fare"] * 0.22, 2)
        r["base_fare"] = round(r["total_fare"] - r["taxes_fees"], 2)
        r["source"] = "SYNTHETIC_TEST"
        # Force either a peak-window departure date or a T+1 horizon so the
        # spike is "explained" demand, not unexplained gouging.
        if i % 2 == 0:
            r["departure_date"] = peak_start.strftime("%Y-%m-%d")
        else:
            r["advance_days"] = 1
        r["true_label"] = "Surge"
        injected.append(r)
    return pd.DataFrame(injected)


def run_backtest():
    conn = sqlite3.connect(DB_FILE)
    quotes, routes = load_data(conn)
    conn.close()

    if quotes.empty or routes.empty:
        print("[!] No data found — run seed_database.py first.")
        return

    quotes_with_route = quotes.merge(
        routes[["origin", "destination"]], on=["origin", "destination"], how="inner"
    )

    gouging_df = inject_gouging_cases(quotes_with_route, N_GOUGING_CASES)
    surge_df = inject_surge_cases(quotes_with_route, N_SURGE_CASES)
    normal_sample_ids = quotes_with_route.sample(
        n=min(N_NORMAL_SAMPLE, len(quotes_with_route)), random_state=3
    )["id"].tolist()

    quotes["true_label"] = "Normal"
    quotes.loc[quotes["id"].isin(normal_sample_ids), "true_label"] = "Normal (control)"

    combined_quotes = pd.concat(
        [quotes, gouging_df.drop(columns=["true_label"], errors="ignore").assign(
            true_label="Gouging"
        ) if not gouging_df.empty else gouging_df,
         surge_df.drop(columns=["true_label"], errors="ignore").assign(
            true_label="Surge"
        ) if not surge_df.empty else surge_df],
        ignore_index=True,
    )
    # Re-attach true_label cleanly (concat above can be fragile with dtypes)
    combined_quotes = pd.concat([quotes, gouging_df, surge_df], ignore_index=True, sort=False)
    combined_quotes["true_label"] = combined_quotes["true_label"].fillna("Normal")

    # Run the REAL pipeline from train_ml_engine.py on this combined set.
    df = engineer_features(combined_quotes.drop(columns=["true_label"]), routes)
    df["true_label"] = combined_quotes["true_label"].values
    df = train_and_score(df)
    df["ml_classification"] = df.apply(classify_surge_vs_gouging, axis=1)

    gouging_rows = df[df["true_label"] == "Gouging"]
    surge_rows = df[df["true_label"] == "Surge"]
    normal_rows = df[df["true_label"].isin(["Normal", "Normal (control)"])]

    gouging_caught = int((gouging_rows["ml_classification"] == "Potential Gouging").sum())
    gouging_caught_as_anomaly = int(gouging_rows["is_anomaly"].sum())
    surge_caught = int((surge_rows["ml_classification"] == "Expected Surge").sum())
    surge_caught_as_anomaly = int(surge_rows["is_anomaly"].sum())
    normal_false_positives = int(normal_rows["is_anomaly"].sum())

    n_gouging = len(gouging_rows)
    n_surge = len(surge_rows)
    n_normal = len(normal_rows)

    report = {
        "generated_at": datetime.datetime.now().isoformat(),
        "method": (
            "Injected synthetic fares with known ground-truth labels into real "
            "seeded data, ran the identical train_ml_engine.py pipeline, and "
            "measured whether injected cases were caught."
        ),
        "gouging_cases": {
            "injected": n_gouging,
            "caught_as_anomaly": gouging_caught_as_anomaly,
            "correctly_labeled_gouging": gouging_caught,
            "recall_as_anomaly": round(gouging_caught_as_anomaly / n_gouging, 3) if n_gouging else None,
            "recall_exact_label": round(gouging_caught / n_gouging, 3) if n_gouging else None,
        },
        "surge_cases": {
            "injected": n_surge,
            "caught_as_anomaly": surge_caught_as_anomaly,
            "correctly_labeled_surge": surge_caught,
            "recall_as_anomaly": round(surge_caught_as_anomaly / n_surge, 3) if n_surge else None,
            "recall_exact_label": round(surge_caught / n_surge, 3) if n_surge else None,
        },
        "normal_control": {
            "sampled": n_normal,
            "false_positives": normal_false_positives,
            "false_positive_rate": round(normal_false_positives / n_normal, 3) if n_normal else None,
        },
    }

    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    print("=" * 60)
    print("SKYLITICS ML ENGINE — BACKTEST / VALIDATION REPORT")
    print("=" * 60)
    print(f"Injected gouging cases:   {n_gouging}")
    print(f"  -> flagged as anomaly:  {gouging_caught_as_anomaly} ({report['gouging_cases']['recall_as_anomaly']*100:.1f}%)")
    print(f"  -> labeled 'Gouging':   {gouging_caught} ({report['gouging_cases']['recall_exact_label']*100:.1f}%)")
    print()
    print(f"Injected surge cases:     {n_surge}")
    print(f"  -> flagged as anomaly:  {surge_caught_as_anomaly} ({report['surge_cases']['recall_as_anomaly']*100:.1f}%)")
    print(f"  -> labeled 'Surge':     {surge_caught} ({report['surge_cases']['recall_exact_label']*100:.1f}%)")
    print()
    print(f"Normal control sample:    {n_normal}")
    print(f"  -> false positives:     {normal_false_positives} ({report['normal_control']['false_positive_rate']*100:.1f}%)")
    print()
    print(f"Full report written to: {REPORT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    run_backtest()
