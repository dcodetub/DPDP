"""
crawler.py
----------
Functional Requirement 2 — Website Crawler.

A same-domain, breadth-first crawler that:
  - Starts from the supplied homepage.
  - Follows internal links only by default.
  - Prioritizes privacy/policy/contact/registration/login/account/cookie pages.
  - Respects robots.txt and a configured page-per-scan limit.
  - Stores URL, HTTP status, title, timestamp, and extracted text per page.

Screenshot capture and JS-rendered crawling (Playwright) are introduced in
a later phase (FR6, Form & Consent Scanner) — Phase 1 uses a plain HTTP
client, which is sufficient for static/server-rendered pages and link
discovery.
"""

import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urldefrag

import httpx
from bs4 import BeautifulSoup

try:
    from app.config import settings
    from app.robots import RobotsChecker
except ModuleNotFoundError:
    from config import settings
    from robots import RobotsChecker

logger = logging.getLogger(__name__)

MAX_STORED_TEXT_CHARS = 200_000  # guard against pathologically large pages


@dataclass
class CrawledPage:
    url: str
    status_code: int | None
    title: str | None
    content_hash: str | None
    content_text: str | None
    discovery_method: str
    priority_match: str | None
    fetch_error: str | None = None
    crawled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CrawlResult:
    pages: list[CrawledPage]
    pages_crawled: int
    stopped_reason: str  # 'page_limit_reached' | 'queue_exhausted' | 'error'


def _priority_rank(url: str) -> int:
    """Lower rank = higher crawl priority. Non-priority pages rank last."""
    lower = url.lower()
    for i, kw in enumerate(settings.PRIORITY_KEYWORDS):
        if kw in lower:
            return i
    return len(settings.PRIORITY_KEYWORDS)


def _matched_keyword(url: str) -> str | None:
    lower = url.lower()
    for kw in settings.PRIORITY_KEYWORDS:
        if kw in lower:
            return kw
    return None


def _is_internal(link: str, approved_domain: str) -> bool:
    netloc = urlparse(link).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc == approved_domain


def _extract_links(html: str, base_url: str, approved_domain: str) -> list[str]:
    """Parse HTML and return absolute, internal, deduplicated links."""
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        absolute, _ = urldefrag(absolute)  # drop #fragment
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if _is_internal(absolute, approved_domain):
            links.add(absolute.rstrip("/"))

    return list(links)


def _extract_title_and_text(html: str) -> tuple[str | None, str]:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Strip obvious navigation/boilerplate noise before extracting text (FR4-adjacent
    # normalization; full normalization pipeline lands in Phase 2).
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()

    text = " ".join(soup.get_text(separator=" ").split())
    return title, text[:MAX_STORED_TEXT_CHARS]


class Crawler:
    """Breadth-first, priority-ordered crawler bounded to a single domain."""

    def __init__(self, start_url: str, approved_domain: str, page_limit: int | None = None):
        self.start_url = start_url.rstrip("/")
        self.approved_domain = approved_domain
        self.page_limit = page_limit or settings.MAX_PAGES_PER_SCAN

    def run(self) -> CrawlResult:
        """Execute the crawl synchronously and return all crawled pages.

        Intended to be invoked from a background task/worker, not directly
        inside a request-handling coroutine (Phase 1 keeps this simple;
        a queue-based async worker is introduced with the Docker workers
        layer in Section 16).
        """
        pages: list[CrawledPage] = []
        visited: set[str] = set()
        queue: deque[tuple[str, str]] = deque([(self.start_url, "homepage")])
        stopped_reason = "queue_exhausted"

        headers = {"User-Agent": settings.USER_AGENT}

        with httpx.Client(headers=headers, follow_redirects=True, timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
            robots = RobotsChecker(self.start_url)
            robots.load(client)

            while queue:
                if len(visited) >= self.page_limit:
                    stopped_reason = "page_limit_reached"
                    break

                # Re-sort the frontier each pass so priority pages (privacy,
                # contact, consent, etc. per FR2) are fetched before generic ones.
                queue = deque(sorted(queue, key=lambda item: _priority_rank(item[0])))
                url, discovery_method = queue.popleft()

                if url in visited:
                    continue
                visited.add(url)

                if not robots.can_fetch(url):
                    logger.info("Skipping (robots.txt disallow): %s", url)
                    continue

                page = self._fetch_one(client, url, discovery_method)
                pages.append(page)

                if page.fetch_error is None and page.status_code and page.status_code < 400:
                    html = self._last_html
                    if html:
                        for link in _extract_links(html, url, self.approved_domain):
                            if link not in visited:
                                queue.append((link, "internal_link"))

                time.sleep(settings.CRAWL_DELAY_SECONDS)  # polite rate limiting

        return CrawlResult(pages=pages, pages_crawled=len(pages), stopped_reason=stopped_reason)

    def _fetch_one(self, client: httpx.Client, url: str, discovery_method: str) -> CrawledPage:
        self._last_html: str | None = None
        try:
            resp = client.get(url)
        except httpx.HTTPError as e:
            logger.warning("Fetch failed for %s: %s", url, e)
            return CrawledPage(
                url=url, status_code=None, title=None, content_hash=None,
                content_text=None, discovery_method=discovery_method,
                priority_match=_matched_keyword(url), fetch_error=str(e),
            )

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and resp.text:
            # Non-HTML (e.g. PDF) — Phase 2 (Document Extraction) handles these
            # via PyMuPDF. Phase 1 records the page but doesn't parse the body.
            return CrawledPage(
                url=url, status_code=resp.status_code, title=None,
                content_hash=hashlib.sha256(resp.content).hexdigest(),
                content_text=None, discovery_method=discovery_method,
                priority_match=_matched_keyword(url),
                fetch_error=f"Non-HTML content-type: {content_type or 'unknown'}",
            )

        self._last_html = resp.text
        title, text = _extract_title_and_text(resp.text)
        content_hash = hashlib.sha256(resp.content).hexdigest()

        return CrawledPage(
            url=url,
            status_code=resp.status_code,
            title=title,
            content_hash=content_hash,
            content_text=text,
            discovery_method=discovery_method,
            priority_match=_matched_keyword(url),
        )
