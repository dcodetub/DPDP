"""
models.py
---------
SQLAlchemy ORM models for the Phase 1 entities defined in Section 17
of the design doc: Company, Scan, Page. Later phases add Document,
Form, Tracker, Finding, Evidence, Score, Report on top of this schema.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship

try:
    from app.database import Base
except ModuleNotFoundError:
    from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScanStatus(str, enum.Enum):
    """Section 19 — Scan State Machine (Phase 1 subset).

    Later phases extend this with DOCUMENT_ANALYSIS, FORM_ANALYSIS,
    TRACKER_ANALYSIS, COMPARISON, SCORING, REPORTING, COMPLETED, and
    their corresponding FAILED_* states.
    """
    QUEUED = "QUEUED"
    CRAWLING = "CRAWLING"
    CRAWL_COMPLETE = "CRAWL_COMPLETE"
    FAILED_CRAWL = "FAILED_CRAWL"


class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=True)
    domain = Column(String, nullable=False, index=True)
    sector = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    scans = relationship("Scan", back_populates="company", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True, default=_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    status = Column(Enum(ScanStatus), nullable=False, default=ScanStatus.QUEUED)
    scan_profile = Column(String, default="Public DPDP MVP")
    scanner_version = Column(String, default="0.1.0-phase1")

    pages_crawled = Column(Integer, default=0)
    page_limit = Column(Integer, default=50)

    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    company = relationship("Company", back_populates="scans")
    pages = relationship("Page", back_populates="scan", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"

    id = Column(String, primary_key=True, default=_uuid)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)

    url = Column(String, nullable=False)
    status_code = Column(Integer, nullable=True)
    title = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    content_text = Column(Text, nullable=True)

    discovery_method = Column(String, nullable=True)   # e.g. 'homepage', 'internal_link'
    priority_match = Column(String, nullable=True)      # matched keyword, if any (FR2/FR3)
    fetch_error = Column(Text, nullable=True)

    crawled_at = Column(DateTime(timezone=True), default=_now)

    scan = relationship("Scan", back_populates="pages")
