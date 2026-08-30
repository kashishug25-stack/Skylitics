"""
Centralized selectors, one block per source.

Keeping selectors here (instead of scattered through scraper.py) means that
when a real site changes its DOM, you only edit this file, not the scraping
logic itself.
"""

MOCK_SITE = {
    "origin_input": "#origin",
    "destination_input": "#destination",
    "date_input": "#depart-date",
    "passengers_select": "#passengers",
    "cabin_select": "#cabin",
    "search_button": "#search-btn",

    "loading_indicator": "#loading",
    "results_container": "#results-container",
    "results_list": '[data-testid="results-list"]',
    "no_results": '[data-testid="no-results"]',
    "flight_card": '[data-testid="flight-card"]',

    "captcha_block": "#captcha-block",
    "captcha_confirm_button": "#captcha-confirm-btn",

    # Fields inside a single flight card, relative to the card element.
    "field_airline": '[data-field="airline"]',
    "field_flight_number": '[data-field="flight-number"]',
    "field_departure_time": '[data-field="departure-time"]',
    "field_arrival_time": '[data-field="arrival-time"]',
    "field_duration": '[data-field="duration"]',
    "field_stops": '[data-field="stops"]',
    "field_price": '[data-field="price"]',
    "field_currency": '[data-field="currency"]',
    "field_provider": '[data-field="provider"]',

    "unexpected_error": "#unexpected-error",
}
