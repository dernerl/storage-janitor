#!/usr/bin/env python3
"""disk-scan — Belegungs-Scan des Data-Volumes für das Treemap-Dashboard (à la WinDirStat).

Läuft mit root-Rechten, wenn ein sudo-Ticket vorhanden ist (`sudo -n`, nie Passwort-Prompt),
sonst als User — dann landen nicht lesbare Bereiche unter „Nicht erfasst“. Der root-Kindprozess
schreibt sein JSON in einen vom User geöffneten File-Descriptor, damit nichts in `scans/`
root gehört.

Output: scans/latest.json (Baum + Metadaten), scans/<stamp>.json (Rotation), scans/growth.json.
"""
from __future__ import annotations

import argparse
import heapq
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SELF = Path(__file__).resolve()
SCANS = SELF.parent / "scans"
LOCK = SCANS / ".scan.lock"
PROGRESS = SCANS / ".progress"
ROOT = "/System/Volumes/Data"
KEEP_SCANS = 14

# Pruning: ein Kind bleibt als eigener Knoten, wenn es relativ zum Parent groß genug ist
# (Größe oder Dateianzahl) und absolut nicht winzig — der Rest wird zu „(N weitere)“.
MIN_SIZE = 10 * 1024**2
MIN_FILES = 2000
REL = 0.01
MAX_CHILDREN = 40
TOP_FILES = 100

CATEGORIES = ["Caches", "Entwicklung", "Apps", "Medien", "Dokumente", "System", "Sonstiges"]
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".heic", ".gif", ".mov", ".mp4", ".m4v", ".avi", ".mkv",
             ".mp3", ".m4a", ".wav", ".aac", ".flac", ".raw", ".cr2", ".arw", ".dng", ".psd"}
DOC_EXT = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pages", ".numbers",
           ".key", ".txt", ".md", ".csv", ".zip"}
DEV_EXT = {".safetensors", ".gguf", ".bin", ".onnx", ".pt", ".whl", ".so", ".dylib", ".a", ".o"}


def category(path: str, is_file: bool, inherited: int) -> int:
    p = path.lower()
    if is_file:
        ext = os.path.splitext(p)[1]
        if ext in MEDIA_EXT:
            return 3
        if ext in DEV_EXT:
            return 1
        if ext in DOC_EXT:
            return 4
    if "/caches" in p or "/.cache" in p or "/.npm" in p or "/cache/" in p:
        return 0
    if ("/library/developer" in p or "node_modules" in p or "/.git" in p or "/projects" in p
            or "/opt/homebrew" in p or "/.venv" in p or "/.local" in p or "/go/" in p
            or "/.bun" in p or "/.cargo" in p or "/.rustup" in p or "/.nvm" in p):
        return 1
    if p.endswith(".app") or ".app/" in p or "/applications" in p or "/application support" in p:
        return 2
    if "/pictures" in p or "/movies" in p or "/music" in p:
        return 3
    if "/documents" in p or "/desktop" in p or "/downloads" in p or "/mobile documents" in p:
        return 4
    if p.startswith(("/system/volumes/data/private", "/system/volumes/data/library",
                     "/system/volumes/data/system", "/system/volumes/data/usr")):
        return 5
    return inherited


class Scanner:
    def __init__(self, root: str):
        self.root = root
        self.dev = os.lstat(root).st_dev
        self.seen_inodes: set[int] = set()
        self.top_files: list[tuple[int, str]] = []  # min-heap (size, path)
        self.unreadable: list[str] = []
        self.files = 0
        self.last_progress = 0.0

    def progress(self) -> None:
        now = time.monotonic()
        if now - self.last_progress > 1.0:
            self.last_progress = now
            print(f"progress {self.files}", file=sys.stderr, flush=True)

    def scan(self, path: str, name: str, cat: int) -> dict:
        """Post-order: liefert {n, s, f, k, c?} — s = belegte Bytes, f = Dateien rekursiv."""
        node_cat = category(path, False, cat)
        children: list[dict] = []
        own_size = 0
        own_files = 0
        big_files: list[dict] = []
        try:
            it = os.scandir(path)
        except OSError:
            if len(self.unreadable) < 500:
                self.unreadable.append(path)
            return {"n": name, "s": 0, "f": 0, "k": node_cat, "x": 1}
        with it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                if e.is_dir(follow_symlinks=False):
                    if st.st_dev != self.dev:
                        continue  # anderes Volume gemountet (z.B. /Volumes/*) — nicht mitzählen
                    children.append(self.scan(e.path, e.name, node_cat))
                    continue
                if st.st_nlink > 1:
                    if st.st_ino in self.seen_inodes:
                        continue
                    self.seen_inodes.add(st.st_ino)
                size = st.st_blocks * 512
                own_size += size
                own_files += 1
                self.files += 1
                if size >= MIN_SIZE:
                    big_files.append({"n": e.name, "s": size, "f": 1,
                                      "k": category(e.path, True, node_cat), "file": 1})
                    if len(self.top_files) < TOP_FILES:
                        heapq.heappush(self.top_files, (size, e.path))
                    elif size > self.top_files[0][0]:
                        heapq.heapreplace(self.top_files, (size, e.path))
        self.progress()

        size = own_size + sum(c["s"] for c in children)
        files = own_files + sum(c["f"] for c in children)
        node = {"n": name, "s": size, "f": files, "k": node_cat}
        candidates = children + big_files
        if candidates:
            node["c"] = prune(candidates, size, files)
        return node


def prune(candidates: list[dict], size: int, files: int) -> list[dict]:
    keep, rest = [], []
    for c in sorted(candidates, key=lambda c: -c["s"]):
        big = c["s"] >= max(MIN_SIZE, size * REL)
        many = not c.get("file") and c["f"] >= max(MIN_FILES, files * REL)
        (keep if (big or many) and len(keep) < MAX_CHILDREN else rest).append(c)
    rest_size = size - sum(c["s"] for c in keep)
    rest_files = files - sum(c["f"] for c in keep)
    if rest_size > 0 or rest_files > 0:
        # Kategorie des Rests = die der größten verworfenen Kinder; ohne Kinder die des Parents
        k = rest[0]["k"] if rest else (keep[0]["k"] if keep else 6)
        keep.append({"n": f"({len(rest)} weitere · lose Dateien)" if rest else "(Dateien)",
                     "s": max(rest_size, 0), "f": max(rest_files, 0), "k": k, "rest": 1})
    return keep


def volume_usage() -> dict:
    """Container-Größe/-frei per statvfs, Data-Volume-Belegung per df (statvfs kennt nur den Container)."""
    vfs = os.statvfs(ROOT)
    total = vfs.f_blocks * vfs.f_frsize
    free = vfs.f_bavail * vfs.f_frsize
    data_used = 0
    try:
        out = subprocess.run(["df", "-k", ROOT], capture_output=True, text=True).stdout.splitlines()
        data_used = int(out[1].split()[2]) * 1024
    except (IndexError, ValueError):
        pass
    return {"total": total, "free": free, "data_used": data_used}


def run_scan() -> dict:
    t0 = time.monotonic()
    sc = Scanner(ROOT)
    tree = sc.scan(ROOT, "Data-Volume", 6)
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "privileged": os.geteuid() == 0,
        "duration_s": round(time.monotonic() - t0, 1),
        "root": ROOT,
        "tree": tree,
        "top_files": [{"p": p, "s": s} for s, p in sorted(sc.top_files, reverse=True)],
        "unreadable": sc.unreadable,
    }


# ── Wachstum ─────────────────────────────────────────────────────────────────
def flatten(node: dict, prefix: str, out: dict) -> None:
    path = f"{prefix}/{node['n']}" if prefix else node["n"]
    if not node.get("rest"):
        out[path] = (node["s"], node["f"])
    for c in node.get("c", []):
        flatten(c, path, out)


def annotate_growth(node: dict, prefix: str, old: dict) -> None:
    path = f"{prefix}/{node['n']}" if prefix else node["n"]
    if not node.get("rest"):
        node["d"] = node["s"] - old.get(path, (0, 0))[0]
    for c in node.get("c", []):
        annotate_growth(c, path, old)


def growth_list(new: dict, old: dict, sign: int, limit: int) -> list[dict]:
    """Ordner mit der größten Änderung — ohne Vorfahren, deren Änderung schon ein einzelnes
    Kind zu ≥80 % erklärt (sonst stünde ~/.cache/uv auch als ~/.cache, ~, /Users in der Liste)."""
    deltas = {p: (s - old.get(p, (0, 0))[0], f - old.get(p, (0, 0))[1]) for p, (s, f) in new.items()}
    for p, (s, f) in old.items():
        if p not in new:
            deltas[p] = (-s, -f)
    rows = []
    for p, (d, df) in deltas.items():
        if d * sign < MIN_SIZE:
            continue
        explained = any(q.startswith(p + "/") and q.count("/") == p.count("/") + 1
                        and deltas[q][0] * sign >= 0.8 * d * sign for q in deltas)
        if not explained:
            rows.append({"p": p, "d": d, "df": df, "s": new.get(p, (0, 0))[0]})
    return sorted(rows, key=lambda r: -r["d"] * sign)[:limit]


# ── Orchestrierung ───────────────────────────────────────────────────────────
def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def lock_pid() -> int | None:
    try:
        pid = int(LOCK.read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if pid_alive(pid) else None


def scan_age_hours() -> float | None:
    try:
        return (time.time() - (SCANS / "latest.json").stat().st_mtime) / 3600
    except OSError:
        return None


def collect() -> dict:
    """Scan als root (sudo -n) wenn möglich, sonst als User. Fortschritt → scans/.progress."""
    if os.geteuid() != 0 and subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0:
        tmp = SCANS / ".scan.tmp"
        with open(tmp, "w") as out:
            p = subprocess.Popen(["sudo", "-n", sys.executable, str(SELF), "--stdout"],
                                 stdout=out, stderr=subprocess.PIPE, text=True)
            for line in p.stderr:
                if line.startswith("progress "):
                    PROGRESS.write_text(line.split()[1])
            p.wait()
        try:
            if p.returncode == 0:
                return json.loads(tmp.read_text())
        finally:
            tmp.unlink(missing_ok=True)
        print("sudo-Scan fehlgeschlagen — Fallback auf User-Scan", file=sys.stderr)

    real_stderr = sys.stderr

    class ProgressTee:
        def write(self, s: str) -> None:
            if s.startswith("progress "):
                PROGRESS.write_text(s.split()[1])
            else:
                real_stderr.write(s)

        def flush(self) -> None:
            real_stderr.flush()

    sys.stderr = ProgressTee()
    try:
        return run_scan()
    finally:
        sys.stderr = real_stderr


def main() -> int:
    ap = argparse.ArgumentParser(description="Belegungs-Scan für das Storage-Dashboard")
    ap.add_argument("--stdout", action="store_true", help="intern: nur scannen, JSON auf stdout")
    ap.add_argument("--background", action="store_true", help="detached starten und sofort zurückkehren")
    ap.add_argument("--max-age-hours", type=float, help="nur scannen, wenn der letzte Scan älter ist")
    args = ap.parse_args()

    if args.stdout:
        json.dump(run_scan(), sys.stdout, separators=(",", ":"))
        return 0

    SCANS.mkdir(exist_ok=True)
    age = scan_age_hours()
    if args.max_age_hours is not None and age is not None and age < args.max_age_hours:
        return 0
    if lock_pid():
        print("Scan läuft bereits", file=sys.stderr)
        return 0

    if args.background:
        cmd = [sys.executable, str(SELF)]
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return 0

    LOCK.write_text(str(os.getpid()))
    try:
        scan = collect()
        scan["volume"] = volume_usage()

        previous = SCANS / "latest.json"
        old: dict = {}
        if previous.exists():
            try:
                prev = json.loads(previous.read_text())
                flatten(prev["tree"], "", old)
                scan["previous_generated"] = prev.get("generated")
            except (OSError, ValueError, KeyError):
                pass
        new: dict = {}
        flatten(scan["tree"], "", new)
        if old:  # erster Scan: kein Vergleich, sonst wäre alles „gewachsen“
            annotate_growth(scan["tree"], "", old)
        growth = {"generated": scan["generated"], "since": scan.get("previous_generated"),
                  "grown": growth_list(new, old, 1, 30) if old else [],
                  "shrunk": growth_list(new, old, -1, 15) if old else []}

        stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
        body = json.dumps(scan, separators=(",", ":"), ensure_ascii=False)
        (SCANS / f"{stamp}.json").write_text(body, encoding="utf-8")
        tmp = SCANS / "latest.json.tmp"
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(previous)
        (SCANS / "growth.json").write_text(json.dumps(growth, ensure_ascii=False, indent=1), encoding="utf-8")
        for f in sorted(SCANS.glob("20*.json"))[:-KEEP_SCANS]:
            f.unlink()

        t = scan["tree"]
        print(f"{t['f']:,} Dateien · {t['s'] / 1e9:.1f} GB · {scan['duration_s']} s · "
              f"{'root' if scan['privileged'] else 'User (ohne sudo)'} · "
              f"{len(body) / 1e6:.2f} MB JSON · {len(scan['unreadable'])} nicht lesbar")
    finally:
        LOCK.unlink(missing_ok=True)
        PROGRESS.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    sys.exit(main())
