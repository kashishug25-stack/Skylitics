import sqlite3
import json
import csv
from datetime import datetime

DB_FILE = "airfare_intelligence.db"

# Official DGCA-derived route weights (must sum to 1.0)
DGCA_WEIGHTS = {
    "DEL-BOM": 0.2299,
    "DEL-BLR": 0.1651,
    "BOM-BLR": 0.1305,
    "DEL-CCU": 0.1158,
    "BLR-HYD": 0.1000,
    "MAA-DEL": 0.0953,
    "DEL-GOI": 0.0889,
    "DEL-PAT": 0.0745,
}

STATUTORY_CAPS = [7500, 9000, 10500, 12000]
TRACKED_AIRLINES = ["IndiGo", "Air India", "SpiceJet", "Akasa Air"]
PREDATORY_MULTIPLE = 2.0


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def load_economy_quotes():
    """Loads all real Economy-class fare quotes, grouped by corridor."""
    conn = get_db()
    rows = conn.execute("""
        SELECT origin, destination, departure_date, advance_days,
               airline, flight_number, cabin_class, total_fare
        FROM cleaned_fare_quotes
        WHERE cabin_class = 'Economy'
    """).fetchall()
    conn.close()

    by_corridor = {}
    for r in rows:
        corridor = f"{r['origin']}-{r['destination']}"
        by_corridor.setdefault(corridor, []).append(dict(r))
    return by_corridor


def compute_corridor_baseline(fares):
    """Real median fare for a corridor, used as the fair-pricing benchmark."""
    sorted_fares = sorted(fares)
    n = len(sorted_fares)
    if n == 0:
        return None
    mid = n // 2
    if n % 2 == 0:
        return (sorted_fares[mid - 1] + sorted_fares[mid]) / 2
    return sorted_fares[mid]


def simulate_tariff_cap(by_corridor, cap):
    """
    Clamps every Economy fare in every corridor to the cap, recalculates each
    corridor's average, then recomputes the National Laspeyres Index using
    real DGCA weights. Only corridors present in DGCA_WEIGHTS are counted,
    and weights actually used are re-normalized so they still sum to 1.0
    even if a corridor has zero real quotes (keeps the index mathematically valid).
    """
    corridor_avgs_original = {}
    corridor_avgs_capped = {}

    for corridor in DGCA_WEIGHTS:
        fares = [q["total_fare"] for q in by_corridor.get(corridor, [])]
        if not fares:
            continue
        original_avg = sum(fares) / len(fares)
        capped_fares = [min(f, cap) for f in fares]
        capped_avg = sum(capped_fares) / len(capped_fares)
        corridor_avgs_original[corridor] = original_avg
        corridor_avgs_capped[corridor] = capped_avg

    available_weight = sum(DGCA_WEIGHTS[c] for c in corridor_avgs_original)
    if available_weight == 0:
        return None

    # National index = 100 at the pre-cap (original) average, per corridor,
    # weighted by re-normalized DGCA weight. This mirrors a real Laspeyres
    # fixed-base index where the base period is "before the cap."
    index_before = 0.0
    index_after = 0.0
    for corridor, orig_avg in corridor_avgs_original.items():
        norm_weight = DGCA_WEIGHTS[corridor] / available_weight
        capped_avg = corridor_avgs_capped[corridor]
        index_before += norm_weight * 100.0
        index_after += norm_weight * (capped_avg / orig_avg) * 100.0

    reduction_bps = round((index_before - index_after) * 100, 1)  # basis points

    return {
        "cap_inr": cap,
        "corridors_included": list(corridor_avgs_original.keys()),
        "corridors_missing_data": [c for c in DGCA_WEIGHTS if c not in corridor_avgs_original],
        "national_index_before_cap": round(index_before, 2),
        "national_index_after_cap": round(index_after, 2),
        "inflation_reduction_bps": reduction_bps,
        "corridor_detail": {
            c: {
                "original_avg_fare": round(corridor_avgs_original[c], 2),
                "capped_avg_fare": round(corridor_avgs_capped[c], 2),
                "flights_affected": sum(1 for q in by_corridor[c] if q["total_fare"] > cap),
                "total_flights": len(by_corridor[c]),
            }
            for c in corridor_avgs_original
        },
    }


def run_compliance_audit(by_corridor):
    """
    Flags any Economy quote priced above PREDATORY_MULTIPLE x its own
    corridor's real median fare, then builds a per-airline scorecard.
    """
    non_compliant_flights = []
    airline_stats = {a: {"total_quotes": 0, "violations": 0, "excess_margin": 0.0} for a in TRACKED_AIRLINES}
    airline_stats["Other"] = {"total_quotes": 0, "violations": 0, "excess_margin": 0.0}

    for corridor, quotes in by_corridor.items():
        fares = [q["total_fare"] for q in quotes]
        baseline = compute_corridor_baseline(fares)
        if baseline is None:
            continue
        fair_benchmark = baseline
        threshold = fair_benchmark * PREDATORY_MULTIPLE

        for q in quotes:
            airline = q["airline"] if q["airline"] in TRACKED_AIRLINES else "Other"
            airline_stats[airline]["total_quotes"] += 1

            if q["total_fare"] > threshold:
                excess = q["total_fare"] - fair_benchmark
                airline_stats[airline]["violations"] += 1
                airline_stats[airline]["excess_margin"] += excess

                non_compliant_flights.append({
                    "Airline": q["airline"],
                    "Flight_No": q["flight_number"],
                    "Route": corridor,
                    "Date": q["departure_date"],
                    "Total_Fare": q["total_fare"],
                    "Fair_Benchmark": round(fair_benchmark, 2),
                    "Surge_Multiple": round(q["total_fare"] / fair_benchmark, 2),
                })

    scorecard = {}
    for airline, stats in airline_stats.items():
        total = stats["total_quotes"]
        violations = stats["violations"]
        compliance_pct = round(100 * (1 - violations / total), 2) if total > 0 else None
        scorecard[airline] = {
            "total_quotes": total,
            "violations": violations,
            "compliance_percentage": compliance_pct,
            "total_excess_tariff_margin_inr": round(stats["excess_margin"], 2),
        }

    return scorecard, non_compliant_flights


def main():
    print("Loading real Economy-class fare quotes from airfare_intelligence.db ...")
    by_corridor = load_economy_quotes()

    total_quotes = sum(len(v) for v in by_corridor.values())
    print(f"Loaded {total_quotes} real Economy quotes across {len(by_corridor)} corridors.")

    weight_sum = round(sum(DGCA_WEIGHTS.values()), 4)
    if weight_sum != 1.0:
        print(f"WARNING: DGCA_WEIGHTS sum to {weight_sum}, not 1.0 — check the weights.")

    print("\nRunning statutory tariff-cap simulations ...")
    cap_results = []
    for cap in STATUTORY_CAPS:
        result = simulate_tariff_cap(by_corridor, cap)
        if result:
            cap_results.append(result)
            print(f"  Cap ₹{cap}: index {result['national_index_before_cap']} -> "
                  f"{result['national_index_after_cap']} "
                  f"({result['inflation_reduction_bps']} bps reduction)")

    print("\nRunning airline compliance & fair-pricing audit "
          f"(predatory threshold = {PREDATORY_MULTIPLE}x corridor median) ...")
    scorecard, non_compliant = run_compliance_audit(by_corridor)
    for airline, stats in scorecard.items():
        print(f"  {airline}: {stats['violations']}/{stats['total_quotes']} violations "
              f"({stats['compliance_percentage']}% compliant)")

    report = {
        "generated_at": datetime.now().isoformat(),
        "total_economy_quotes_analyzed": total_quotes,
        "dgca_weight_sum_check": weight_sum,
        "tariff_cap_scenarios": cap_results,
        "airline_compliance_scorecard": scorecard,
        "total_non_compliant_flights": len(non_compliant),
    }

    with open("regulatory_audit_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\nWrote regulatory_audit_report.json")

    with open("audit_export.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Airline", "Flight_No", "Route", "Date", "Total_Fare",
            "Fair_Benchmark", "Surge_Multiple"
        ])
        writer.writeheader()
        writer.writerows(non_compliant)
    print(f"Wrote audit_export.csv ({len(non_compliant)} non-compliant flights)")


if __name__ == "__main__":
    main()