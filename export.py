"""
export.py
---------
Export helpers for scan results (CSV / JSON). Supports the "Export"
action in the GUI so a scan's crawled-page data can be downloaded and
shared outside the tool.
"""

import csv
import io
import json
from datetime import datetime


def scan_to_dict(scan, pages) -> dict:
    """Serialize a Scan + its Pages into a plain dict for JSON export."""
    return {
        "scan_id": scan.id,
        "status": scan.status.value if hasattr(scan.status, "value") else scan.status,
        "pages_crawled": scan.pages_crawled,
        "page_limit": scan.page_limit,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "pages": [
            {
                "url": p.url,
                "status_code": p.status_code,
                "title": p.title,
                "discovery_method": p.discovery_method,
                "priority_match": p.priority_match,
                "fetch_error": p.fetch_error,
                "crawled_at": p.crawled_at.isoformat() if p.crawled_at else None,
            }
            for p in pages
        ],
    }


def export_json(scan, pages) -> str:
    """Return a pretty-printed JSON string of the scan + pages."""
    return json.dumps(scan_to_dict(scan, pages), indent=2)


def export_csv(scan, pages) -> str:
    """Return a CSV string (one row per crawled page)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "url", "status_code", "title", "discovery_method",
        "priority_match", "fetch_error", "crawled_at",
    ])
    for p in pages:
        writer.writerow([
            p.url,
            p.status_code or "",
            p.title or "",
            p.discovery_method or "",
            p.priority_match or "",
            p.fetch_error or "",
            p.crawled_at.isoformat() if p.crawled_at else "",
        ])
    return buffer.getvalue()
