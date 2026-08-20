"""
config.py
---------
Central configuration for the DPDP Public Readiness Scanner (Phase 1).

Values can be overridden via environment variables of the same name
(e.g. DATABASE_URL, MAX_PAGES_PER_SCAN).
"""

import os
import sys


def _default_db_path() -> str:
    """Resolve where the SQLite file should live.

    When running as a PyInstaller-frozen executable, sys.executable
    points at DPDP_Scanner.exe itself — we store the DB alongside it
    so data persists across runs (PyInstaller's onefile temp extraction
    folder is wiped after the app closes and must never hold data).
    Otherwise, use the project root (one level above app/).
    """
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    db_path = os.path.join(app_dir, "dpdp_scanner.db")
    return db_path.replace(os.sep, "/")  # SQLite URLs use forward slashes


class Settings:
    # ── Database ──────────────────────────────────────────────────────────────
    # Defaults to local SQLite for easy MVP bring-up. Point DATABASE_URL at a
    # PostgreSQL DSN in staging/production per the target architecture
    # (Section 16: PostgreSQL for companies/scans/findings/metadata).
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{_default_db_path()}")

    # ── Crawler ───────────────────────────────────────────────────────────────
    MAX_PAGES_PER_SCAN: int = int(os.getenv("MAX_PAGES_PER_SCAN", "50"))          # FR2 default
    REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
    CRAWL_DELAY_SECONDS: float = float(os.getenv("CRAWL_DELAY_SECONDS", "0.5"))    # polite rate limit
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "DPDPReadinessScanner/1.0 (+https://example.com/scanner-info)"
    )

    # ── Priority keywords (FR2: prioritize these page types in crawl order) ───
    PRIORITY_KEYWORDS: list[str] = [
        "privacy", "policy", "data-protection", "personal-data",
        "cookie", "contact", "register", "signup", "sign-up",
        "login", "signin", "sign-in", "account", "terms",
    ]

    # ── Allowed schemes (FR1: HTTPS only by default) ───────────────────────────
    ALLOWED_SCHEMES: tuple[str, ...] = ("https",)
    ALLOW_HTTP_FALLBACK: bool = os.getenv("ALLOW_HTTP_FALLBACK", "false").lower() == "true"

    # ── Concurrent scans (Section 22 non-functional target) ────────────────────
    MAX_CONCURRENT_SCANS: int = int(os.getenv("MAX_CONCURRENT_SCANS", "5"))


settings = Settings()
