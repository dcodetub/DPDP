"""
robots.py
---------
Fetches and evaluates a site's robots.txt so the crawler can respect it,
per FR2 ("Respect robots.txt and configured crawl limits") and
Section 21 ("Respect robots.txt where applicable").
"""

import logging
from urllib.robotparser import RobotFileParser

import httpx

try:
    from app.config import settings
except ModuleNotFoundError:
    from config import settings

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Wraps RobotFileParser with a graceful fallback if robots.txt is
    missing or unreachable (default: allow crawling in that case)."""

    def __init__(self, base_url: str):
        self._parser = RobotFileParser()
        self._loaded = False
        self._robots_url = self._build_robots_url(base_url)

    @staticmethod
    def _build_robots_url(base_url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def load(self, client: httpx.Client) -> None:
        """Fetch and parse robots.txt. Safe to call once before crawling starts."""
        try:
            resp = client.get(self._robots_url, timeout=settings.REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                self._parser.parse(resp.text.splitlines())
                logger.info("Loaded robots.txt from %s", self._robots_url)
            else:
                logger.info(
                    "robots.txt returned status %d at %s — defaulting to allow.",
                    resp.status_code, self._robots_url
                )
        except httpx.HTTPError as e:
            logger.info("Could not fetch robots.txt (%s) — defaulting to allow.", e)
        finally:
            self._loaded = True

    def can_fetch(self, url: str) -> bool:
        """Return True if the given URL is allowed to be crawled.

        If robots.txt could not be loaded, defaults to allowing the fetch
        (fail-open) rather than blocking the whole scan.
        """
        if not self._loaded:
            return True
        try:
            return self._parser.can_fetch(settings.USER_AGENT, url)
        except Exception:
            return True
