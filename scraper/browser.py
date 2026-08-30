"""
Playwright browser lifecycle management.

Keeping this separate from scraper.py means the orchestration logic doesn't
need to know anything about launch args, headless mode, timeouts, etc.
"""

import logging
from contextlib import contextmanager
from playwright.sync_api import sync_playwright

logger = logging.getLogger("skylitics.browser")

DEFAULT_TIMEOUT_MS = 15_000


@contextmanager
def launch_browser(headless: bool = True):
    """
    Context manager that yields a ready-to-use Playwright Page.

    Usage:
        with launch_browser(headless=True) as page:
            page.goto("https://example.com")
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        logger.info("Browser launched (headless=%s)", headless)
        try:
            yield page
        finally:
            context.close()
            browser.close()
            logger.info("Browser closed")
