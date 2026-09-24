#!/usr/bin/env python3
"""Localhost-Server für das Storage-Dashboard.

Statt `python3 -m http.server` (wie beim workbench-janitor) ein kleiner eigener Server, weil
das Dashboard zwei Aktionen braucht: einen Scan starten und eine Datei im Finder zeigen.
Bindet nur an 127.0.0.1; POSTs nur mit passendem Origin (kein Auslösen von fremden Seiten).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent
REPO = DASHBOARD.parent
SCANS = REPO / "scans"
SCANNER = REPO / "disk-scan.py"
PORT = int(os.environ.get("STORAGE_DASHBOARD_PORT", "8935"))
ALLOWED_ORIGINS = {f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"}
DATA_ROOT = "/System/Volumes/Data"


def scan_running() -> bool:
    try:
        os.kill(int((SCANS / ".scan.lock").read_text().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def status() -> dict:
    meta: dict = {"running": scan_running(), "progress_files": None, "sudo_ticket": False}
    try:
        meta["progress_files"] = int((SCANS / ".progress").read_text())
    except (OSError, ValueError):
        pass
    meta["sudo_ticket"] = subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0
    return meta


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD), **kwargs)

    def log_message(self, *args) -> None:
        pass

    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0]
        if clean.startswith("/scans/"):
            name = Path(clean).name
            if name in {"latest.json", "growth.json"}:
                return str(SCANS / name)
            return str(DASHBOARD / "__nicht_vorhanden__")
        if clean in {"/", "/index.html"}:
            return str(DASHBOARD / "index.html")
        return str(DASHBOARD / "__nicht_vorhanden__")  # nur index.html + Scan-JSON ausliefern

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/api/status":
            return self.send_json(200, status())
        return super().do_GET()

    def do_POST(self) -> None:
        if self.headers.get("Origin") not in ALLOWED_ORIGINS:
            return self.send_json(403, {"error": "origin"})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send_json(400, {"error": "json"})

        if self.path == "/api/scan":
            if not scan_running():
                subprocess.run([sys.executable, str(SCANNER), "--background"], cwd=REPO)
            return self.send_json(202, {"started": True})

        if self.path == "/api/reveal":
            path = os.path.realpath(str(body.get("path", "")))
            if not path.startswith(DATA_ROOT + "/") or not os.path.exists(path):
                return self.send_json(404, {"error": "path"})
            subprocess.run(["open", "-R", path])
            return self.send_json(200, {"ok": True})

        return self.send_json(404, {"error": "unknown"})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
