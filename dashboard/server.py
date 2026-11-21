#!/usr/bin/env python3
"""Localhost-Server für das Storage-Dashboard.

Statt `python3 -m http.server` (wie beim workbench-janitor) ein kleiner eigener Server, weil
das Dashboard Aktionen braucht: Scan starten, im Finder zeigen, löschen (Papierkorb oder
endgültig) und ein paar feste macOS-Ziele öffnen.
Bindet nur an 127.0.0.1; POSTs nur mit passendem Origin (kein Auslösen von fremden Seiten).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent
REPO = DASHBOARD.parent
SCANS = REPO / "scans"
SCANNER = REPO / "disk-scan.py"
REPORTS = REPO / "reports"
PORT = int(os.environ.get("STORAGE_DASHBOARD_PORT", "8935"))
ALLOWED_ORIGINS = {f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"}
DATA_ROOT = "/System/Volumes/Data"
HOME = DATA_ROOT + str(Path.home())
# Feste Ziele für /api/open — keine freien Pfade oder URLs vom Client
OPEN_TARGETS = {
    "trash": [str(Path.home() / ".Trash")],
    "storage": ["x-apple.systempreferences:com.apple.settings.Storage"],
}


def history() -> dict:
    """Chronik: Scan-Zeilen aus history.jsonl + Tageswerte des Janitors (letzter Lauf pro Tag,
    `df -g` → ganze GiB) als dichtere Linie für „Belegt“."""
    scans = []
    try:
        for line in (SCANS / "history.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                scans.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    daily = []
    for f in sorted(REPORTS.glob("20??-??-??.md")):
        try:
            m = re.search(r"Freier Speicher: `([\d.]+) GB` / `([\d.]+) GB`", f.read_text(encoding="utf-8"))
        except OSError:
            continue
        if m and float(m.group(2)) > 0:
            free, total = float(m.group(1)) * 2**30, float(m.group(2)) * 2**30
            daily.append({"t": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds"),
                          "used": total - free, "free": free})
    return {"scans": scans, "daily": daily}


def deletable(path: str) -> bool:
    """Löschen nur im Home (ab 2 Ebenen, also nicht ~/Library selbst) und für Programme unter
    /Applications (eine .app, die nicht in einer anderen .app steckt). Spiegelt deletable() im Frontend."""
    if path.startswith(HOME + "/"):
        return len(Path(path).relative_to(HOME).parts) >= 2
    apps = DATA_ROOT + "/Applications/"
    if not path.startswith(apps):
        return False
    parts = Path(path).relative_to(apps).parts
    return parts[-1].endswith(".app") and not any(p.endswith(".app") for p in parts[:-1])


def remove(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def scan_running() -> bool:
    try:
        os.kill(int((SCANS / ".scan.lock").read_text().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def status() -> dict:
    meta: dict = {"running": scan_running(), "progress_files": None, "sudo_ticket": False, "home": HOME}
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
        if self.path == "/api/history":
            return self.send_json(200, history())
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

        if self.path == "/api/trash":
            raw = os.path.normpath(str(body.get("path", "")))  # „~/a/..“ darf nicht als ~/a durchgehen
            # Elternordner auflösen, letztes Glied nicht — ein Symlink wird selbst gelöscht, nicht sein Ziel
            path = os.path.join(os.path.realpath(os.path.dirname(raw)), os.path.basename(raw))
            if not deletable(path):
                return self.send_json(403, {"error": "Dieser Bereich ist zum Löschen gesperrt."})
            if not os.path.lexists(path):
                return self.send_json(404, {"error": "Nicht gefunden — seit dem Scan schon gelöscht?"})
            if body.get("permanent"):
                try:
                    remove(path)
                except OSError as e:
                    return self.send_json(500, {"error": f"Löschen fehlgeschlagen: {e.strerror}"})
            else:
                r = subprocess.run(["/usr/bin/trash", "-s", path], capture_output=True, text=True)
                if r.returncode or os.path.lexists(path):
                    return self.send_json(500, {"error": "Papierkorb fehlgeschlagen: " + (r.stderr.strip() or "keine Berechtigung?")})
            return self.send_json(200, {"ok": True})

        if self.path == "/api/open":
            target = OPEN_TARGETS.get(str(body.get("target")))
            if not target:
                return self.send_json(404, {"error": "target"})
            subprocess.run(["open", *target])
            return self.send_json(200, {"ok": True})

        return self.send_json(404, {"error": "unknown"})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
