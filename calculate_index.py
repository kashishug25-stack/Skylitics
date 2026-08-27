"""
calculate_index.py — MoSPI / DGCA Laspeyres Price Index Aggregator
Calculates corridor price relatives, horizon decay, and national composite index.
"""

import sqlite3
import datetime

DB_FILE = "airfare_intelligence.db"

def compute_airfare_index():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 1. Fetch Route Basket and DGCA Traffic Weights
    cursor.execute("SELECT origin, destination, route_name, route_weight, base_tariff_inr FROM route_basket WHERE is_active = 1")
    routes = cursor.fetchall()

    results = {}
    national_composite = {1: 0.0, 7: 0.0, 15: 0.0, 30: 0.0, 45: 0.0}
    now = datetime.datetime.now().isoformat()

    for origin, dest, route_name, weight, base_tariff in routes:
        corridor = f"{origin}-{dest}"
        results[corridor] = {
            "origin": origin,
            "destination": dest,
            "route_name": route_name,
            "weight": weight,
            "base_tariff": base_tariff,
            "horizons": {}
        }

        for days in [1, 7, 15, 30, 45]:
            cursor.execute("""
            SELECT total_fare FROM cleaned_fare_quotes 
            WHERE origin = ? AND destination = ? AND advance_days = ?
            ORDER BY total_fare ASC
            """, (origin, dest, days))
            
            fares = [row[0] for row in cursor.fetchall()]
            if not fares:
                continue

            # Calculate Median Fare (removes outlier distortion)
            mid = len(fares) // 2
            median_fare = fares[mid] if len(fares) % 2 != 0 else (fares[mid - 1] + fares[mid]) / 2.0

            # Laspeyres Price Relative = (Current Median / Base Period Tariff) * 100
            price_relative = round((median_fare / base_tariff) * 100.0, 2)
            
            # Dynamic Surge Classification
            if price_relative >= 135.0:
                surge_status = "Surge Spike"
            elif price_relative >= 105.0:
                surge_status = "Moderate"
            else:
                surge_status = "Optimal Base"

            results[corridor]["horizons"][days] = {
                "median_fare": round(median_fare, 2),
                "price_relative": price_relative,
                "surge_status": surge_status
            }

            # Add to traffic-weighted national composite index
            national_composite[days] += price_relative * weight

            # Record calculation in database
            cursor.execute("""
            INSERT INTO computed_price_index 
            (computed_at, corridor, advance_days, median_fare, base_fare, price_relative, laspeyres_index, surge_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, corridor, days, median_fare, base_tariff, price_relative, round(price_relative * weight, 2), surge_status))

    conn.commit()
    conn.close()

    for d in national_composite:
        national_composite[d] = round(national_composite[d], 2)

    return {"national_composite_index": national_composite, "corridors": results}

if __name__ == "__main__":
    data = compute_airfare_index()
    print("=" * 60)
    print("✈️  VIMANSUCHAK LASPEYRES PRICE INDEX ENGINE")
    print("=" * 60)
    print(f"National Composite Index (T+1 Immediate): {data['national_composite_index'][1]}")
    print(f"National Composite Index (T+7 Standard):  {data['national_composite_index'][7]}")
    print(f"National Composite Index (T+15 Advance):  {data['national_composite_index'][15]}")
    print(f"National Composite Index (T+30 Window):   {data['national_composite_index'][30]}")
    print(f"National Composite Index (T+45 Long):     {data['national_composite_index'][45]}")
    print("=" * 60)
    print("✅ Index Calculation Successful.")