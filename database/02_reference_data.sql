-- ============================================================
-- SKYLYTICS
-- DEVELOPMENT REFERENCE DATA
-- ============================================================
-- IMPORTANT:
-- This is temporary development/test reference data.
-- It is NOT the final list of airlines or scraping sources.
-- Replace/update it once the team finalizes the real sources.
-- ============================================================


-- ============================================================
-- 1. AIRPORTS
-- ============================================================

INSERT INTO airports
    (iata_code, airport_name, city_name, state, country,
     latitude, longitude, is_metro, is_active)
VALUES
    ('DEL', 'Indira Gandhi International Airport',
     'Delhi', 'Delhi', 'India',
     28.5562, 77.1000, TRUE, TRUE),

    ('BOM', 'Chhatrapati Shivaji Maharaj International Airport',
     'Mumbai', 'Maharashtra', 'India',
     19.0896, 72.8656, TRUE, TRUE),

    ('BLR', 'Kempegowda International Airport',
     'Bengaluru', 'Karnataka', 'India',
     13.1986, 77.7066, TRUE, TRUE),

    ('HYD', 'Rajiv Gandhi International Airport',
     'Hyderabad', 'Telangana', 'India',
     17.2403, 78.4294, TRUE, TRUE),

    ('MAA', 'Chennai International Airport',
     'Chennai', 'Tamil Nadu', 'India',
     12.9941, 80.1709, TRUE, TRUE),

    ('CCU', 'Netaji Subhas Chandra Bose International Airport',
     'Kolkata', 'West Bengal', 'India',
     22.6547, 88.4467, TRUE, TRUE),

    ('AMD', 'Sardar Vallabhbhai Patel International Airport',
     'Ahmedabad', 'Gujarat', 'India',
     23.0732, 72.6347, TRUE, TRUE),

    ('GOI', 'Manohar International Airport',
     'Goa', 'Goa', 'India',
     15.7443, 73.8636, FALSE, TRUE);


-- ============================================================
-- 2. AIRLINES
-- ============================================================
-- Development-only list.
-- Final airline selection will be decided by the team later.

INSERT INTO airlines
    (iata_code, icao_code, airline_name, carrier_type, is_active)
VALUES
    ('6E', 'IGO', 'IndiGo', 'LCC', TRUE),

    ('AI', 'AIC', 'Air India', 'FSC', TRUE),

    ('SG', 'SEJ', 'SpiceJet', 'LCC', TRUE),

    ('QP', 'AKJ', 'Akasa Air', 'LCC', TRUE);


-- ============================================================
-- 3. SOURCES
-- ============================================================
-- These records describe potential data sources.
--
-- IMPORTANT:
-- robots_txt_checked / terms_checked / api_available
-- are NOT being marked TRUE merely because the source exists.
-- The team must verify these separately before actual scraping.

INSERT INTO sources
    (source_name, source_type, base_url,
     robots_txt_checked, terms_checked, api_available,
     rate_limit_secs, is_active)
VALUES
    ('Development Airline Source',
     'AIRLINE_DIRECT',
     NULL,
     FALSE,
     FALSE,
     FALSE,
     5,
     TRUE),

    ('Development OTA Source',
     'OTA',
     NULL,
     FALSE,
     FALSE,
     FALSE,
     5,
     TRUE);


-- ============================================================
-- 4. ROUTES
-- ============================================================
-- Routes reference airport IDs rather than repeating airport data.
--
-- We obtain the airport IDs using their IATA codes.

INSERT INTO routes
    (origin_airport_id, dest_airport_id, distance_km,
     route_name, is_active)
SELECT
    origin.airport_id,
    destination.airport_id,
    route_data.distance_km,
    route_data.route_name,
    TRUE
FROM
(
    VALUES
        ('DEL', 'BOM', 1148.0, 'DEL-BOM'),
        ('BOM', 'DEL', 1148.0, 'BOM-DEL'),
        ('DEL', 'BLR', 1740.0, 'DEL-BLR'),
        ('BLR', 'DEL', 1740.0, 'BLR-DEL'),
        ('DEL', 'HYD', 1250.0, 'DEL-HYD'),
        ('HYD', 'DEL', 1250.0, 'HYD-DEL'),
        ('BOM', 'BLR', 845.0, 'BOM-BLR'),
        ('BLR', 'BOM', 845.0, 'BLR-BOM'),
        ('DEL', 'MAA', 1760.0, 'DEL-MAA'),
        ('MAA', 'DEL', 1760.0, 'MAA-DEL'),
        ('BOM', 'HYD', 620.0, 'BOM-HYD'),
        ('HYD', 'BOM', 620.0, 'HYD-BOM')
) AS route_data
(
    origin_code,
    destination_code,
    distance_km,
    route_name
)
JOIN airports origin
    ON origin.iata_code = route_data.origin_code
JOIN airports destination
    ON destination.iata_code = route_data.destination_code
ON CONFLICT (origin_airport_id, dest_airport_id)
DO NOTHING;


-- ============================================================
-- END OF DEVELOPMENT REFERENCE DATA
-- ============================================================