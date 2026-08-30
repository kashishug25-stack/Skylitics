"""Custom exceptions so scraper.py can handle each failure mode distinctly."""


class ScraperError(Exception):
    """Base class for all scraper-related errors."""


class CaptchaDetectedError(ScraperError):
    """Raised when a CAPTCHA / access-challenge is detected on the page.

    Per project policy: we NEVER attempt to solve or bypass this. We only
    detect it, log it, and either pause for manual completion or terminate
    gracefully.
    """


class NoResultsError(ScraperError):
    """Raised when the search legitimately returned zero flights."""


class UnexpectedPageStructureError(ScraperError):
    """Raised when the results area doesn't match any known state
    (not results, not empty, not CAPTCHA) — the page structure likely changed."""


class SearchTimeoutError(ScraperError):
    """Raised when the page fails to respond within the expected time."""
