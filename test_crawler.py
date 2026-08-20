"""
tests/test_crawler.py
----------------------
Covers FR2 — Website Crawler: internal-link extraction, priority
ordering, and end-to-end crawl behaviour against a mocked site (respx).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import respx
import pytest

from app.crawler import _extract_links, _priority_rank, _matched_keyword, Crawler


SAMPLE_HTML = """
<html>
<head><title>Example Homepage</title></head>
<body>
  <nav>
    <a href="/privacy-policy">Privacy Policy</a>
    <a href="/about">About</a>
    <a href="https://external-site.com/page">External</a>
  </nav>
  <a href="/contact">Contact Us</a>
  <a href="mailto:hello@example.com">Email</a>
  <a href="/about#section2">About (fragment)</a>
</body>
</html>
"""


class TestExtractLinks:
    def test_extracts_internal_links_only(self):
        links = _extract_links(SAMPLE_HTML, "https://example.com", "example.com")
        assert "https://example.com/privacy-policy" in links
        assert "https://example.com/about" in links
        assert "https://example.com/contact" in links

    def test_excludes_external_links(self):
        links = _extract_links(SAMPLE_HTML, "https://example.com", "example.com")
        assert not any("external-site.com" in link for link in links)

    def test_excludes_mailto(self):
        links = _extract_links(SAMPLE_HTML, "https://example.com", "example.com")
        assert not any(link.startswith("mailto:") for link in links)

    def test_deduplicates_fragment_variants(self):
        links = _extract_links(SAMPLE_HTML, "https://example.com", "example.com")
        about_links = [l for l in links if "about" in l]
        assert len(about_links) == 1  # '/about' and '/about#section2' collapse to one


class TestPriorityRank:
    def test_privacy_ranks_above_generic_page(self):
        assert _priority_rank("https://example.com/privacy-policy") < _priority_rank("https://example.com/products")

    def test_contact_is_a_priority_page(self):
        assert _matched_keyword("https://example.com/contact-us") == "contact"

    def test_generic_page_has_no_match(self):
        assert _matched_keyword("https://example.com/products") is None


@respx.mock
class TestCrawlerRun:
    def test_respects_page_limit(self):
        respx.get("https://example.com").mock(
            return_value=httpx.Response(200, text=SAMPLE_HTML, headers={"content-type": "text/html"})
        )
        respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(404))
        respx.get(url__regex=r"https://example\.com/.*").mock(
            return_value=httpx.Response(200, text="<html><head><title>Sub</title></head><body></body></html>",
                                         headers={"content-type": "text/html"})
        )

        crawler = Crawler(start_url="https://example.com", approved_domain="example.com", page_limit=2)
        result = crawler.run()

        assert result.pages_crawled <= 2
        assert result.stopped_reason in ("page_limit_reached", "queue_exhausted")

    def test_handles_fetch_failure_gracefully(self):
        respx.get("https://broken.com").mock(side_effect=httpx.ConnectError("boom"))
        respx.get("https://broken.com/robots.txt").mock(return_value=httpx.Response(404))

        crawler = Crawler(start_url="https://broken.com", approved_domain="broken.com", page_limit=5)
        result = crawler.run()

        assert result.pages_crawled == 1
        assert result.pages[0].fetch_error is not None
