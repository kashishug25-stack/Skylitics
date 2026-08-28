
"""
Skylitics PostgreSQL API Server

This API reads data from the PostgreSQL database
and provides it to the frontend/dashboard.

Database:
    PostgreSQL

Database name:
    airfare_index
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from db import get_db_connection


# ============================================================
# CREATE FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Skylitics Airfare Price Index API",
    description=(
        "API for accessing Skylitics PostgreSQL airfare data "
        "for the Airfare Price Index dashboard."
    ),
    version="1.1.0"
)


# ============================================================
# CORS
# ============================================================
# The dashboard is currently a read-only client.
# Credentials/cookies are not required.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():
    return {
        "project": "Skylitics",
        "status": "API is running",
        "database": "PostgreSQL",
        "database_name": "airfare_index",
        "documentation": "/docs"
    }


# ============================================================
# DATABASE HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health_check():

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT 1;")
        result = cursor.fetchone()

        cursor.close()
        connection.close()

        return {
            "status": "healthy",
            "database": "connected",
            "test": result[0]
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


# ============================================================
# AIRLINES
# ============================================================

@app.get("/api/airlines")
def get_airlines():

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                airline_id,
                iata_code,
                icao_code,
                airline_name,
                carrier_type,
                is_active
            FROM airlines
            ORDER BY airline_name;
        """)

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        airlines = []

        for row in rows:
            airlines.append({
                "airline_id": row[0],
                "iata_code": row[1],
                "icao_code": row[2],
                "airline_name": row[3],
                "carrier_type": row[4],
                "is_active": row[5]
            })

        return {
            "count": len(airlines),
            "data": airlines
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# AIRPORTS
# ============================================================

@app.get("/api/airports")
def get_airports():

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                airport_id,
                iata_code,
                airport_name,
                city_name,
                state,
                country,
                latitude,
                longitude,
                is_metro,
                is_active
            FROM airports
            ORDER BY city_name;
        """)

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        airports = []

        for row in rows:
            airports.append({
                "airport_id": row[0],
                "iata_code": row[1],
                "airport_name": row[2],
                "city_name": row[3],
                "state": row[4],
                "country": row[5],
                "latitude": (
                    float(row[6])
                    if row[6] is not None
                    else None
                ),
                "longitude": (
                    float(row[7])
                    if row[7] is not None
                    else None
                ),
                "is_metro": row[8],
                "is_active": row[9]
            })

        return {
            "count": len(airports),
            "data": airports
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# SOURCES
# ============================================================

@app.get("/api/sources")
def get_sources():

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                source_id,
                source_name,
                source_type,
                base_url,
                robots_txt_checked,
                terms_checked,
                api_available,
                rate_limit_secs,
                is_active
            FROM sources
            ORDER BY source_name;
        """)

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        sources = []

        for row in rows:
            sources.append({
                "source_id": row[0],
                "source_name": row[1],
                "source_type": row[2],
                "base_url": row[3],
                "robots_txt_checked": row[4],
                "terms_checked": row[5],
                "api_available": row[6],
                "rate_limit_secs": row[7],
                "is_active": row[8]
            })

        return {
            "count": len(sources),
            "data": sources
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# ROUTES
# ============================================================

@app.get("/api/routes")
def get_routes():

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                r.route_id,
                r.route_name,
                r.distance_km,
                r.is_active,

                o.iata_code AS origin_code,
                o.city_name AS origin_city,

                d.iata_code AS destination_code,
                d.city_name AS destination_city

            FROM routes r

            JOIN airports o
                ON r.origin_airport_id = o.airport_id

            JOIN airports d
                ON r.dest_airport_id = d.airport_id

            ORDER BY r.route_name;
        """)

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        routes = []

        for row in rows:
            routes.append({
                "route_id": row[0],
                "route_name": row[1],
                "distance_km": (
                    float(row[2])
                    if row[2] is not None
                    else None
                ),
                "is_active": row[3],
                "origin_code": row[4],
                "origin_city": row[5],
                "destination_code": row[6],
                "destination_city": row[7]
            })

        return {
            "count": len(routes),
            "data": routes
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# ROUTE WEIGHTS
# ============================================================

@app.get("/api/route-weights")
def get_route_weights():

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                rw.weight_id,
                rw.route_id,
                r.route_name,
                rw.weight,
                rw.effective_from,
                rw.effective_to,
                rw.source_note

            FROM route_weights rw

            JOIN routes r
                ON rw.route_id = r.route_id

            ORDER BY
                rw.effective_from,
                r.route_name;
        """)

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        weights = []

        for row in rows:
            weights.append({
                "weight_id": row[0],
                "route_id": row[1],
                "route_name": row[2],
                "weight": float(row[3]),
                "effective_from": row[4],
                "effective_to": row[5],
                "source_note": row[6]
            })

        return {
            "count": len(weights),
            "data": weights
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# RAW FARE QUOTES
# ============================================================
# Supports:
#
# /api/fares/raw
#
# /api/fares/raw?route_id=1
#
# /api/fares/raw?route_id=1&limit=50
#
# ============================================================

@app.get("/api/fares/raw")
def get_raw_fares(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000
    ),
    route_id: int | None = Query(
        default=None,
        ge=1
    )
):

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            SELECT
                fq.quote_id,
                fq.job_id,
                sj.route_id,

                fq.airline_id,
                a.airline_name,

                fq.flight_number,
                fq.departure_datetime,
                fq.arrival_datetime,
                fq.fare_class,

                fq.base_fare,
                fq.taxes_fees,
                fq.total_fare,

                fq.seats_status,
                fq.currency,
                fq.is_synthetic,
                fq.scraped_at

            FROM fare_quotes_raw fq

            JOIN scrape_jobs sj
                ON fq.job_id = sj.job_id

            LEFT JOIN airlines a
                ON fq.airline_id = a.airline_id

            WHERE 1 = 1
        """

        parameters = []

        if route_id is not None:
            query += """
                AND sj.route_id = %s
            """
            parameters.append(route_id)

        query += """
            ORDER BY fq.scraped_at DESC
            LIMIT %s;
        """

        parameters.append(limit)

        cursor.execute(
            query,
            tuple(parameters)
        )

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        fares = []

        for row in rows:
            fares.append({
                "quote_id": row[0],
                "job_id": row[1],
                "route_id": row[2],
                "airline_id": row[3],
                "airline_name": row[4],
                "flight_number": row[5],
                "departure_datetime": row[6],
                "arrival_datetime": row[7],
                "fare_class": row[8],
                "base_fare": (
                    float(row[9])
                    if row[9] is not None
                    else None
                ),
                "taxes_fees": (
                    float(row[10])
                    if row[10] is not None
                    else None
                ),
                "total_fare": (
                    float(row[11])
                    if row[11] is not None
                    else None
                ),
                "seats_status": row[12],
                "currency": row[13],
                "is_synthetic": row[14],
                "scraped_at": row[15]
            })

        return {
            "count": len(fares),
            "limit": limit,
            "filters": {
                "route_id": route_id
            },
            "data": fares
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CLEAN FARE QUOTES
# ============================================================
# Supports:
#
# /api/fares/clean
#
# /api/fares/clean?route_id=1
#
# /api/fares/clean?route_id=1&limit=50
#
# ============================================================

@app.get("/api/fares/clean")
def get_clean_fares(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000
    ),
    route_id: int | None = Query(
        default=None,
        ge=1
    )
):

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            SELECT
                fc.clean_id,
                fc.raw_quote_id,
                fc.route_id,
                r.route_name,

                fc.source_id,
                s.source_name,

                fc.airline_id,
                a.airline_name,

                fc.advance_purchase_days,
                fc.travel_date,
                fc.scrape_date,

                fc.base_fare,
                fc.taxes_fees,
                fc.total_fare,
                fc.currency,

                fc.is_outlier,
                fc.is_duplicate,
                fc.is_synthetic

            FROM fare_quotes_clean fc

            JOIN routes r
                ON fc.route_id = r.route_id

            JOIN sources s
                ON fc.source_id = s.source_id

            LEFT JOIN airlines a
                ON fc.airline_id = a.airline_id

            WHERE 1 = 1
        """

        parameters = []

        if route_id is not None:
            query += """
                AND fc.route_id = %s
            """
            parameters.append(route_id)

        query += """
            ORDER BY fc.scrape_date DESC
            LIMIT %s;
        """

        parameters.append(limit)

        cursor.execute(
            query,
            tuple(parameters)
        )

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        fares = []

        for row in rows:
            fares.append({
                "clean_id": row[0],
                "raw_quote_id": row[1],
                "route_id": row[2],
                "route_name": row[3],
                "source_id": row[4],
                "source_name": row[5],
                "airline_id": row[6],
                "airline_name": row[7],
                "advance_purchase_days": row[8],
                "travel_date": row[9],
                "scrape_date": row[10],
                "base_fare": (
                    float(row[11])
                    if row[11] is not None
                    else None
                ),
                "taxes_fees": (
                    float(row[12])
                    if row[12] is not None
                    else None
                ),
                "total_fare": (
                    float(row[13])
                    if row[13] is not None
                    else None
                ),
                "currency": row[14],
                "is_outlier": row[15],
                "is_duplicate": row[16],
                "is_synthetic": row[17]
            })

        return {
            "count": len(fares),
            "limit": limit,
            "filters": {
                "route_id": route_id
            },
            "data": fares
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
# ============================================================
# FARE SUMMARY
# ============================================================

@app.get("/api/fare-summary")
def get_fare_summary(
    route_id: int | None = None
):
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            SELECT
                COUNT(*) AS total_quotes,
                COUNT(DISTINCT airline_id) AS airline_count,
                COUNT(DISTINCT route_id) AS route_count,
                AVG(base_fare) AS average_base_fare,
                AVG(taxes_fees) AS average_taxes_fees,
                AVG(total_fare) AS average_total_fare,
                MIN(total_fare) AS minimum_fare,
                MAX(total_fare) AS maximum_fare
            FROM fare_quotes_clean
            WHERE 1 = 1
        """

        parameters = []

        if route_id is not None:
            query += " AND route_id = %s"
            parameters.append(route_id)

        cursor.execute(query, tuple(parameters))

        row = cursor.fetchone()

        cursor.close()
        connection.close()

        return {
            "route_id": route_id,
            "total_quotes": row[0],
            "airline_count": row[1],
            "route_count": row[2],
            "average_base_fare": (
                float(row[3]) if row[3] is not None else None
            ),
            "average_taxes_fees": (
                float(row[4]) if row[4] is not None else None
            ),
            "average_total_fare": (
                float(row[5]) if row[5] is not None else None
            ),
            "minimum_fare": (
                float(row[6]) if row[6] is not None else None
            ),
            "maximum_fare": (
                float(row[7]) if row[7] is not None else None
            )
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ============================================================
# AIRFARE PRICE INDEX
# ============================================================
#
# Examples:
#
# /api/index
#
# /api/index?frequency=DAILY
#
# /api/index?route_id=1
#
# /api/index?frequency=DAILY&route_id=1
#
# ============================================================

@app.get("/api/index")
def get_index(
    frequency: str | None = Query(
        default=None
    ),
    route_id: int | None = Query(
        default=None,
        ge=1
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000
    )
):

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            SELECT
                ai.index_id,
                ai.frequency,
                ai.period_date,
                ai.route_id,
                r.route_name,

                ai.index_value,
                ai.base_period,

                ai.pct_change_dod,
                ai.pct_change_mom,
                ai.pct_change_yoy,

                ai.num_observations,
                ai.is_synthetic,
                ai.computed_at

            FROM apix_index ai

            LEFT JOIN routes r
                ON ai.route_id = r.route_id

            WHERE 1 = 1
        """

        parameters = []

        if frequency:
            frequency_value = frequency.upper()

            allowed_frequencies = {
                "DAILY",
                "WEEKLY",
                "MONTHLY"
            }

            if frequency_value not in allowed_frequencies:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "frequency must be DAILY, WEEKLY, "
                        "or MONTHLY"
                    )
                )

            query += """
                AND ai.frequency = %s
            """

            parameters.append(
                frequency_value
            )

        if route_id is not None:
            query += """
                AND ai.route_id = %s
            """

            parameters.append(
                route_id
            )

        query += """
            ORDER BY ai.period_date DESC
            LIMIT %s;
        """

        parameters.append(limit)

        cursor.execute(
            query,
            tuple(parameters)
        )

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        indexes = []

        for row in rows:
            indexes.append({
                "index_id": row[0],
                "frequency": row[1],
                "period_date": row[2],
                "route_id": row[3],
                "route_name": row[4],
                "index_value": float(row[5]),
                "base_period": row[6],
                "pct_change_dod": (
                    float(row[7])
                    if row[7] is not None
                    else None
                ),
                "pct_change_mom": (
                    float(row[8])
                    if row[8] is not None
                    else None
                ),
                "pct_change_yoy": (
                    float(row[9])
                    if row[9] is not None
                    else None
                ),
                "num_observations": row[10],
                "is_synthetic": row[11],
                "computed_at": row[12]
            })

        return {
            "count": len(indexes),
            "limit": limit,
            "filters": {
                "frequency": frequency.upper()
                if frequency
                else None,
                "route_id": route_id
            },
            "data": indexes
        }

    except HTTPException:
        raise

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# DGCA MONTHLY AVERAGE FARES
# ============================================================

@app.get("/api/dgca-fares")
def get_dgca_fares():

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                d.record_id,
                d.route_id,
                r.route_name,
                d.month,
                d.avg_fare,
                d.source_doc

            FROM dgca_monthly_avg_fare d

            LEFT JOIN routes r
                ON d.route_id = r.route_id

            ORDER BY d.month DESC;
        """)

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        data = []

        for row in rows:
            data.append({
                "record_id": row[0],
                "route_id": row[1],
                "route_name": row[2],
                "month": row[3],
                "avg_fare": (
                    float(row[4])
                    if row[4] is not None
                    else None
                ),
                "source_doc": row[5]
            })

        return {
            "count": len(data),
            "data": data
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# SCRAPE JOBS
# ============================================================

@app.get("/api/scrape-jobs")
def get_scrape_jobs(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000
    ),
    route_id: int | None = Query(
        default=None,
        ge=1
    )
):

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            SELECT
                sj.job_id,
                sj.route_id,
                r.route_name,

                sj.source_id,
                s.source_name,

                sj.advance_purchase_days,
                sj.scrape_timestamp,
                sj.target_travel_date,
                sj.status,
                sj.error_message,
                sj.scraper_version,
                sj.is_synthetic

            FROM scrape_jobs sj

            JOIN routes r
                ON sj.route_id = r.route_id

            JOIN sources s
                ON sj.source_id = s.source_id

            WHERE 1 = 1
        """

        parameters = []

        if route_id is not None:
            query += """
                AND sj.route_id = %s
            """

            parameters.append(route_id)

        query += """
            ORDER BY sj.scrape_timestamp DESC
            LIMIT %s;
        """

        parameters.append(limit)

        cursor.execute(
            query,
            tuple(parameters)
        )

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        jobs = []

        for row in rows:
            jobs.append({
                "job_id": row[0],
                "route_id": row[1],
                "route_name": row[2],
                "source_id": row[3],
                "source_name": row[4],
                "advance_purchase_days": row[5],
                "scrape_timestamp": row[6],
                "target_travel_date": row[7],
                "status": row[8],
                "error_message": row[9],
                "scraper_version": row[10],
                "is_synthetic": row[11]
            })

        return {
            "count": len(jobs),
            "limit": limit,
            "filters": {
                "route_id": route_id
            },
            "data": jobs
        }

    except Exception as e:

        if connection:
            connection.close()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# END OF SERVER
# ============================================================

