"""
tests/test_url_intake.py
------------------------
Covers FR1 — Company URL Intake: normalization, HTTPS-only enforcement,
scheme rejection, and domain extraction.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.url_intake import validate_and_intake, normalize_url, InvalidURLError


class TestNormalizeUrl:
    def test_adds_https_scheme_if_missing(self):
        assert normalize_url("example.com") == "https://example.com"

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/") == "https://example.com"

    def test_preserves_path(self):
        assert normalize_url("https://example.com/about") == "https://example.com/about"


class TestValidateAndIntake:
    def test_valid_https_url(self):
        result = validate_and_intake("https://example.com")
        assert result.normalized_url == "https://example.com"
        assert result.domain == "example.com"
        assert result.scheme == "https"

    def test_bare_domain_gets_https_added(self):
        result = validate_and_intake("example.com")
        assert result.scheme == "https"

    def test_www_stripped_from_domain(self):
        result = validate_and_intake("https://www.example.com")
        assert result.domain == "example.com"

    def test_rejects_ftp_scheme(self):
        with pytest.raises(InvalidURLError):
            validate_and_intake("ftp://example.com")

    def test_rejects_http_by_default(self):
        with pytest.raises(InvalidURLError):
            validate_and_intake("http://example.com")

    def test_rejects_empty_url(self):
        with pytest.raises(InvalidURLError):
            validate_and_intake("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(InvalidURLError):
            validate_and_intake("   ")

    def test_rejects_malformed_url(self):
        with pytest.raises(InvalidURLError):
            validate_and_intake("https://")
