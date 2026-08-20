"""
schemas.py
----------
Pydantic request/response models for the Phase 1 API surface
(POST /api/scans, GET /api/scans/{id}) per Section 18 — API Outline.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class ScanCreateRequest(BaseModel):
    """FR1 — Company URL Intake input."""
    company_url: str = Field(..., description="Company website URL (mandatory).")
    company_name: str | None = Field(None, description="Company name (optional).")
    sector: str | None = Field(None, description="Industry/sector (optional).")
    scan_profile: str = Field("Public DPDP MVP", description="Scan profile.")
    page_limit: int | None = Field(None, description="Override MAX_PAGES_PER_SCAN for this scan.")


class ScanCreateResponse(BaseModel):
    scan_id: str
    company_id: str
    status: str
    normalized_url: str
    approved_domain: str


class PageOut(BaseModel):
    url: str
    status_code: int | None
    title: str | None
    discovery_method: str | None
    priority_match: str | None
    fetch_error: str | None
    crawled_at: datetime

    model_config = {"from_attributes": True}


class ScanStatusResponse(BaseModel):
    scan_id: str
    status: str
    pages_crawled: int
    page_limit: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    pages: list[PageOut] = []

    model_config = {"from_attributes": True}
