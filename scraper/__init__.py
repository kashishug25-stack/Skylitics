"""
Skylitics scraper package.

Modules:
    models      - FlightOffer data model
    database    - SQLite connection + insert/query helpers
    browser     - Playwright browser lifecycle management
    selectors   - centralized CSS selectors per source (change here, not in scraper.py)
    scraper     - orchestration: run a single search end-to-end
    sources/    - one file per scrape target (mock_site.py, and later real sources)
"""
