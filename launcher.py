"""
launcher.py
-----------
Entry point for the standalone Windows executable (built via PyInstaller,
see BUILD.bat / dpdp_scanner.spec). Not used for normal development —
`uvicorn app.main:app --reload` remains the dev workflow.

Runs the FastAPI app in-process and opens the dashboard in the default
browser once the server is confirmed ready (polls rather than guessing
a fixed delay).
"""

import os
import sys
import threading
import time
import logging
import webbrowser
import urllib.request

# Ensure the bundled app/ package is importable regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.main import app

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def _open_browser_when_ready() -> None:
    for _ in range(60):  # up to ~30 seconds
        time.sleep(0.5)
        try:
            urllib.request.urlopen(URL, timeout=1)
            webbrowser.open(URL)
            return
        except Exception:
            continue
    print(f"Server did not respond in time. Open {URL} manually.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 56)
    print("  DPDP Public Readiness Scanner")
    print(f"  Dashboard : {URL}")
    print("  Close this window to stop the server.")
    print("=" * 56)
    print()

    threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    # log_config=None avoids uvicorn trying to load a logging config file
    # that won't exist inside the frozen bundle.
    uvicorn.run(app, host=HOST, port=PORT, log_level="info", log_config=None)


if __name__ == "__main__":
    main()
