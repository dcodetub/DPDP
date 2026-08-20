"""
url_intake.py
-------------
Functional Requirement 1 — Company URL Intake.

Normalizes and validates a company-supplied URL before a scan is queued:
  - Normalizes the URL (adds scheme if missing, strips trailing slash/fragment).
  - Allows HTTPS only by default (configurable via ALLOW_HTTP_FALLBACK).
  - Rejects unsupported schemes.
  - Determines the "approved domain" the crawler must stay within.
"""

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

try:
    from app.config import settings
except ModuleNotFoundError:
    from config import settings


class InvalidURLError(ValueError):
    """Raised when a supplied URL fails validation."""


@dataclass(frozen=True)
class IntakeResult:
    normalized_url: str
    domain: str          # approved domain the crawler must stay within
    scheme: str


def normalize_url(raw_url: str) -> str:
    """Add a scheme if missing and strip fragments/trailing slashes.

    Args:
        raw_url: URL as typed by the user, e.g. 'example.com' or 'https://example.com/'.

    Returns:
        A normalized absolute URL string.
    """
    raw_url = raw_url.strip()
    if "://" not in raw_url:
        raw_url = f"https://{raw_url}"

    parsed = urlparse(raw_url)
    path = parsed.path.rstrip("/") or ""
    normalized = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    return normalized


def validate_and_intake(raw_url: str) -> IntakeResult:
    """Validate a raw company URL and return the intake result.

    Args:
        raw_url: The company website URL as submitted (FR1 mandatory input).

    Returns:
        IntakeResult with the normalized URL, scheme, and approved domain.

    Raises:
        InvalidURLError: If the URL is malformed or uses a disallowed scheme.
    """
    if not raw_url or not raw_url.strip():
        raise InvalidURLError("Company website URL is required.")

    normalized = normalize_url(raw_url)
    parsed = urlparse(normalized)

    if not parsed.netloc:
        raise InvalidURLError(f"Could not parse a valid host from '{raw_url}'.")

    allowed = set(settings.ALLOWED_SCHEMES)
    if settings.ALLOW_HTTP_FALLBACK:
        allowed.add("http")

    if parsed.scheme not in allowed:
        raise InvalidURLError(
            f"Scheme '{parsed.scheme}' is not permitted. "
            f"Allowed scheme(s): {', '.join(sorted(allowed))}."
        )

    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    return IntakeResult(normalized_url=normalized, domain=domain, scheme=parsed.scheme)
