# DPDP Public Readiness Scanner — Phase 1

**Phase 1 deliverable** (Section 23 of the design doc): URL intake +
crawler + page storage — now with a browser dashboard.

Implements:
- **FR1 — Company URL Intake**: URL normalization, HTTPS-only validation, domain extraction.
- **FR2 — Website Crawler**: same-domain BFS crawl, priority ordering (privacy/contact/consent pages first), robots.txt respect, configurable page limit (default 50), page storage (URL, status, title, timestamp, extracted text).
- **Section 19 (subset) — Scan State Machine**: `QUEUED → CRAWLING → CRAWL_COMPLETE` / `FAILED_CRAWL`.
- **Section 18 (subset) — API Outline**: `POST /api/scans`, `GET /api/scans/{id}`, `GET /api/scans/{id}/export`.
- **Browser dashboard** (`gui/index.html`): start scans, review crawled pages, export results, and a DPDP Act compliance checklist — all served directly by the FastAPI app.

Not yet implemented (future phases per Section 23): document extraction (Phase 2), LLM analysis (Phase 3), form/consent scanning via Playwright (Phase 4), tracker scanning (Phase 5), scoring (Phase 7), reporting (Phase 8).

---

## Quick start (development)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open **http://localhost:8000** — the dashboard loads directly (no
separate frontend server needed; FastAPI serves both the API and the
static GUI). Interactive API docs remain at `/docs`.

---

## Standalone Windows .exe (no install, no dependencies)

For distributing to people who shouldn't need to install Python at all:

**One-time build** (on any Windows machine with Python 3.11+):
```
BUILD.bat
```
This installs PyInstaller, bundles the whole app — Python runtime,
FastAPI, uvicorn, SQLAlchemy, httpx, BeautifulSoup, and the dashboard —
into a single file, and drops it at `dist\DPDP_Scanner.exe`.

**After that**, `DPDP_Scanner.exe` is fully self-contained:
- Copy it anywhere — USB stick, another PC, a shared drive
- Double-click to run — no Python, no pip, no internet required
- It opens a console window (showing the dashboard URL and logs) and
  launches your browser to `http://localhost:8000` automatically
- Its database (`dpdp_scanner.db`) is created next to the `.exe` and
  persists between runs — don't delete it if you want scan history kept

**Why I can't hand you a pre-built `.exe` directly:** PyInstaller has
to build on the same OS it's targeting — it can't cross-compile a
Windows binary from Linux/macOS. `BUILD.bat` does the one-time
Windows-side build for you; from then on, distribution is just copying
the resulting `.exe`.

**Expected size:** the bundled `.exe` is typically 150–250 MB, since it
includes an entire Python runtime plus every dependency.


### Using the dashboard

1. **Overview** — enter a company URL and start a scan.
2. **Scan Results** — the scan ID is carried over automatically; the page polls every 3 seconds while the crawl runs, and stops once complete. Use **Export** to download results as CSV or JSON, or **Print / Save PDF** for a browser-native PDF via your OS print dialog.
3. **Compliance Checklist** — 11 key DPDP Act obligations, each with a one-line summary and an expandable full explanation. Tick the checkbox once you've manually verified your organisation's practice against that clause. Progress is saved in the browser (`localStorage`) and reflected on the Overview page.

### Using the API directly

```bash
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -d '{"company_url": "example.com", "company_name": "Example Corp"}'

curl http://localhost:8000/api/scans/<scan_id>

curl http://localhost:8000/api/scans/<scan_id>/export?format=csv -o scan.csv
curl http://localhost:8000/api/scans/<scan_id>/export?format=json -o scan.json
```

---

## Configuration

All settings in `app/config.py` can be overridden via environment
variables:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./dpdp_scanner.db` | Swap to a PostgreSQL DSN for staging/prod (Section 16). |
| `MAX_PAGES_PER_SCAN` | `50` | FR2 default page limit. |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Per-request HTTP timeout. |
| `CRAWL_DELAY_SECONDS` | `0.5` | Polite delay between requests. |
| `ALLOW_HTTP_FALLBACK` | `false` | FR1: set `true` to permit `http://` (HTTPS-only by default). |
| `MAX_CONCURRENT_SCANS` | `5` | Matches Section 22 non-functional target. |

---

## Architecture notes / what's intentionally simplified for Phase 1

- **Background execution**: uses FastAPI's `BackgroundTasks` (in-process) rather than the Docker worker queue described in Section 16. The crawl logic (`Crawler.run()`) is decoupled from this — swapping to a Celery/RQ worker later means changing only how `run_crawl_job` is invoked, not its internals.
- **HTTP client, not headless browser**: Phase 1 uses `httpx` for static/server-rendered HTML. Playwright-based rendering is introduced in Phase 4 (FR6, Form & Consent Scanner) — needed for JS-heavy pages and interactive forms, not for basic link discovery.
- **SQLite default**: swap `DATABASE_URL` to Postgres for anything beyond local development; the schema (SQLAlchemy models) is portable as-is.
- **No screenshot capture yet**: FR2 mentions screenshot capture for evidence pages — that lands with the Evidence Store in Phase 8, once Playwright is already in the stack from Phase 4.
- **Checklist state is client-side only**: verification checkboxes persist in the browser's `localStorage`, not the database. This keeps Phase 1 schema-free for this feature; a later phase can promote it to a proper `review` table tied to a scan/company if you want checklist state to be shareable across devices or reviewers.
- **Deployment-layout-resilient imports**: every cross-module import (`app.database`, `app.models`, etc.) has a fallback to a flat import, so the code runs correctly whether deployed with `app/` as a nested package or flattened to the container root — see the `try/except ModuleNotFoundError` pattern throughout `app/*.py`.

---

## Project structure

```
dpdp_scanner/
├── app/
│   ├── main.py          # FastAPI app + endpoints + GUI serving
│   ├── config.py         # Settings (env-overridable, frozen-exe-aware)
│   ├── database.py       # SQLAlchemy engine/session
│   ├── models.py         # Company, Scan, Page ORM models
│   ├── schemas.py        # Pydantic request/response models
│   ├── url_intake.py     # FR1 — URL validation & normalization
│   ├── crawler.py        # FR2 — crawler implementation
│   ├── robots.py         # robots.txt fetch + check
│   └── export.py         # CSV / JSON export helpers
├── gui/
│   └── index.html         # Self-contained browser dashboard
├── tests/
│   ├── test_url_intake.py
│   └── test_crawler.py
├── launcher.py            # Entry point for the standalone .exe build
├── dpdp_scanner.spec      # PyInstaller build spec
├── BUILD.bat              # One-time Windows build script
├── requirements.txt
└── README.md
```

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

`test_crawler.py` uses `respx` to mock all HTTP calls — no real network
access is needed to run the test suite.

## Typography credit

The dashboard uses **Source Sans 3**, **Source Serif 4**, and **Source
Code Pro** — all typefaces originally designed and open-sourced by
Adobe.

