"""
main.py
-------
FastAPI application exposing the Phase 1 API surface:

  POST /api/scans          — create + queue a scan (FR1 intake)
  GET  /api/scans/{id}      — get scan status + crawled pages (FR2 output)

Per Section 18 (API Outline). Later phases add /findings, /evidence,
/report, /review, and /rules on top of this same app.
"""

import logging
import os
import sys
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

try:
    from app.database import get_db, init_db
    from app.models import Company, Scan, Page, ScanStatus
    from app.schemas import ScanCreateRequest, ScanCreateResponse, ScanStatusResponse
    from app.url_intake import validate_and_intake, InvalidURLError
    from app.crawler import Crawler
    from app.config import settings
    from app.export import export_json, export_csv
except ModuleNotFoundError:
    from database import get_db, init_db
    from models import Company, Scan, Page, ScanStatus
    from schemas import ScanCreateRequest, ScanCreateResponse, ScanStatusResponse
    from url_intake import validate_and_intake, InvalidURLError
    from crawler import Crawler
    from config import settings
    from export import export_json, export_csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DPDP Public Readiness Scanner — Phase 1 API",
    version="0.1.0-phase1",
    description="URL intake, crawler, and page storage (FR1 + FR2), plus a browser dashboard.",
)

def _resolve_gui_dir() -> str:
    """Locate the gui/ folder in both normal execution and a frozen .exe.

    PyInstaller (onefile mode) extracts bundled data files to a temporary
    directory at runtime, exposed as sys._MEIPASS — that's where gui/
    ends up when running as DPDP_Scanner.exe. In normal `uvicorn
    app.main:app` execution, it's simply the project's gui/ folder.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "gui")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gui")


GUI_DIR = _resolve_gui_dir()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("Database initialised.")


@app.get("/")
def serve_dashboard():
    """Serve the browser dashboard (single self-contained HTML file)."""
    index_path = os.path.join(GUI_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Dashboard not found. Expected gui/index.html.")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/scans", response_model=ScanCreateResponse, status_code=202)
def create_scan(
    payload: ScanCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Validate the submitted URL, persist Company + Scan, and queue crawling.

    Returns 202 Accepted — the crawl runs asynchronously; poll
    GET /api/scans/{id} for progress and results.
    """
    try:
        intake = validate_and_intake(payload.company_url)
    except InvalidURLError as e:
        raise HTTPException(status_code=422, detail=str(e))

    company = db.query(Company).filter(Company.domain == intake.domain).first()
    if company is None:
        company = Company(name=payload.company_name, domain=intake.domain, sector=payload.sector)
        db.add(company)
        db.flush()

    scan = Scan(
        company_id=company.id,
        status=ScanStatus.QUEUED,
        scan_profile=payload.scan_profile,
        page_limit=payload.page_limit or settings.MAX_PAGES_PER_SCAN,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    background_tasks.add_task(
        run_crawl_job, scan.id, intake.normalized_url, intake.domain, scan.page_limit
    )

    return ScanCreateResponse(
        scan_id=scan.id,
        company_id=company.id,
        status=scan.status.value,
        normalized_url=intake.normalized_url,
        approved_domain=intake.domain,
    )


@app.get("/api/scans/{scan_id}", response_model=ScanStatusResponse)
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found.")

    return ScanStatusResponse(
        scan_id=scan.id,
        status=scan.status.value,
        pages_crawled=scan.pages_crawled,
        page_limit=scan.page_limit,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        error_message=scan.error_message,
        pages=list(scan.pages),
    )


@app.get("/api/scans/{scan_id}/export")
def export_scan(scan_id: str, format: str = "json", db: Session = Depends(get_db)):
    """Export a scan's crawled-page results as a downloadable file.

    Args:
        scan_id: The scan to export.
        format: 'json' (default) or 'csv'.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found.")

    pages = list(scan.pages)
    fmt = format.lower().strip()

    if fmt == "csv":
        content = export_csv(scan, pages)
        media_type = "text/csv"
        filename = f"dpdp_scan_{scan_id[:8]}.csv"
    elif fmt == "json":
        content = export_json(scan, pages)
        media_type = "application/json"
        filename = f"dpdp_scan_{scan_id[:8]}.json"
    else:
        raise HTTPException(status_code=400, detail="format must be 'json' or 'csv'.")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def run_crawl_job(scan_id: str, start_url: str, domain: str, page_limit: int) -> None:
    """Background job: run the crawler and persist results.

    Phase 1 runs this as an in-process FastAPI BackgroundTask for
    simplicity. Section 16 specifies Docker-based async workers for
    production — swap this function's invocation for a queue consumer
    (e.g. Celery/RQ task) without changing its internal logic.
    """
    try:
        from app.database import SessionLocal
    except ModuleNotFoundError:
        from database import SessionLocal

    db = SessionLocal()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if scan is None:
            logger.error("Scan %s vanished before crawl could start.", scan_id)
            return

        scan.status = ScanStatus.CRAWLING
        scan.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            crawler = Crawler(start_url=start_url, approved_domain=domain, page_limit=page_limit)
            result = crawler.run()

            for cp in result.pages:
                db.add(Page(
                    scan_id=scan.id,
                    url=cp.url,
                    status_code=cp.status_code,
                    title=cp.title,
                    content_hash=cp.content_hash,
                    content_text=cp.content_text,
                    discovery_method=cp.discovery_method,
                    priority_match=cp.priority_match,
                    fetch_error=cp.fetch_error,
                    crawled_at=cp.crawled_at,
                ))

            scan.pages_crawled = result.pages_crawled
            scan.status = ScanStatus.CRAWL_COMPLETE
            scan.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(
                "Scan %s complete: %d pages (%s).",
                scan_id, result.pages_crawled, result.stopped_reason
            )

        except Exception as e:
            logger.exception("Crawl failed for scan %s", scan_id)
            scan.status = ScanStatus.FAILED_CRAWL
            scan.error_message = str(e)
            scan.completed_at = datetime.now(timezone.utc)
            db.commit()

    finally:
        db.close()
