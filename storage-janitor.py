#!/usr/bin/env python3
"""storage-janitor — Cache-/Speicherplatz-Hygiene für macOS.

Zwei Tiers:
- auto-safe: reine Rebuild-/Download-Caches (Dev-Tools) + Browser-Caches über einer
  konfigurierten Größe. Wird bei jedem Lauf automatisch angewendet.
- recommend-only: verwaiste Cache-Kandidaten + Speicherplatz-Warnschwelle. Wird nur
  gemeldet, nie automatisch gelöscht.

Rührt nie an fremden App-Configs (z.B. Spotify-prefs) und nie an einem Cache, dessen
Prozess gerade läuft.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

SELF_DIR = Path(__file__).resolve().parent
REPORTS = SELF_DIR / "reports"
CACHES = Path.home() / "Library" / "Caches"
RULES_FILE = Path(os.environ.get("STORAGE_JANITOR_RULES", SELF_DIR / "rules.json"))

DATA_VOLUME = "/System/Volumes/Data"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 1, ""


def dir_size_mb(d: Path) -> float:
    if not d.exists():
        return 0.0
    total = 0
    for root, dirs, files in os.walk(d):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / (1024 * 1024)


def load_rules() -> dict:
    try:
        return json.loads(RULES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Konnte {RULES_FILE} nicht laden: {e}", file=sys.stderr)
        return {}


# ── Tier "auto-safe" ─────────────────────────────────────────────────────────
@dataclass
class Trimmed:
    name: str
    method: str
    freed_mb: float


@dataclass
class Skipped:
    name: str
    reason: str


def trim_regenerable(entry: dict, apply: bool) -> tuple[Trimmed | None, Skipped | None]:
    name = entry["name"]
    cache_path = CACHES / entry.get("path", name)
    before = dir_size_mb(cache_path)
    if before < 1.0:
        return None, None  # nichts da, kein Eintrag im Report nötig

    method = entry.get("command")
    if not apply:
        return Trimmed(name=name, method="dry-run", freed_mb=before), None

    if method:
        rc, _ = run(method, timeout=180)
        if rc != 0:
            return None, Skipped(name=name, reason=f"Kommando fehlgeschlagen: {' '.join(method)}")
    else:
        try:
            shutil.rmtree(cache_path)
        except OSError as e:
            return None, Skipped(name=name, reason=f"rm fehlgeschlagen: {e}")

    after = dir_size_mb(cache_path)
    freed = max(before - after, 0.0)
    return Trimmed(name=name, method=(" ".join(method) if method else "rm -rf"), freed_mb=freed), None


def process_running(process_name: str) -> bool:
    rc, _ = run(["pgrep", "-ix", process_name])
    return rc == 0


def trim_capped(entry: dict, apply: bool) -> tuple[Trimmed | None, Skipped | None]:
    name = entry["name"]
    cache_path = CACHES / entry.get("path", name)
    max_mb = float(entry.get("max_size_mb", 1000))
    before = dir_size_mb(cache_path)
    if before <= max_mb:
        return None, None

    proc = entry.get("process_name", name)
    if process_running(proc):
        return None, Skipped(name=name, reason=f"{before:.0f} MB über Limit ({max_mb:.0f} MB), aber {proc} läuft — übersprungen")

    if not apply:
        return Trimmed(name=name, method="dry-run", freed_mb=before - max_mb), None

    try:
        shutil.rmtree(cache_path)
    except OSError as e:
        return None, Skipped(name=name, reason=f"rm fehlgeschlagen: {e}")

    after = dir_size_mb(cache_path)
    freed = max(before - after, 0.0)
    return Trimmed(name=name, method="rm -rf (über Limit)", freed_mb=freed), None


# ── Tier "recommend-only" ────────────────────────────────────────────────────
BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+){2,}$")


def installed_bundle_ids() -> set[str]:
    rc, out = run(["mdfind", "kMDItemContentType == 'com.apple.application-bundle'"], timeout=60)
    ids: set[str] = set()
    if rc != 0:
        return ids
    for app_path in out.splitlines():
        rc2, bid = run(["mdls", "-name", "kMDItemCFBundleIdentifier", "-raw", app_path])
        if rc2 == 0 and bid and bid != "(null)":
            ids.add(bid)
    return ids


def find_orphan_candidates(known_names: set[str], min_mb: float) -> list[dict]:
    candidates = []
    bundle_ids: set[str] | None = None  # lazy, nur wenn gebraucht

    for entry in sorted(CACHES.iterdir()):
        if not entry.is_dir() or entry.name in known_names:
            continue
        if entry.name.startswith("com.apple."):
            continue  # System-eigene Caches nie anfassen

        size_mb = dir_size_mb(entry)
        if size_mb < min_mb:
            continue

        if BUNDLE_ID_RE.match(entry.name):
            if bundle_ids is None:
                bundle_ids = installed_bundle_ids()
            if entry.name in bundle_ids:
                continue
            candidates.append({"name": entry.name, "size_mb": round(size_mb, 1),
                                "reason": "Bundle-ID nicht unter installierten Apps gefunden"})
        elif "." not in entry.name and entry.name.islower():
            # CLI-Tool-Namen sind konventionell klein geschrieben (ollama, brew, pnpm, …) —
            # TitleCase-Namen wie "CloudKit"/"GeoServices" sind macOS-Frameworks, keine
            # PATH-Kommandos, und würden hier nur falsch-positiv landen.
            # `command -v` ist ein Shell-Builtin, kein PATH-Executable — über zsh -lc prüfen
            rc, _ = run(["zsh", "-lc", f"command -v {entry.name}"])
            if rc == 0:
                continue
            candidates.append({"name": entry.name, "size_mb": round(size_mb, 1),
                                "reason": f"kein Kommando '{entry.name}' auf PATH gefunden"})
    return candidates


def disk_space() -> tuple[float, float]:
    rc, out = run(["df", "-g", DATA_VOLUME])
    if rc != 0:
        return 0.0, 0.0
    lines = out.splitlines()
    if len(lines) < 2:
        return 0.0, 0.0
    parts = lines[1].split()
    # Filesystem Size Used Avail Capacity iused ifree %iused Mounted
    try:
        total_gb = float(parts[1])
        avail_gb = float(parts[3])
        return total_gb, avail_gb
    except (IndexError, ValueError):
        return 0.0, 0.0


# ── Output ───────────────────────────────────────────────────────────────────
def build_report(trimmed: list[Trimmed], skipped: list[Skipped], orphans: list[dict],
                  total_gb: float, free_gb: float, warn_gb: float, critical_gb: float,
                  applied: bool) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = [f"# 🧺 Storage Janitor — {now}", "",
           f"Freier Speicher: `{free_gb:.1f} GB` / `{total_gb:.1f} GB` · "
           f"{'angewendet' if applied else 'dry-run'}", ""]

    if free_gb <= critical_gb:
        out += [f"## 🔴 Speicherplatz kritisch ({free_gb:.1f} GB frei, Schwelle {critical_gb:.0f} GB)", ""]
    elif free_gb <= warn_gb:
        out += [f"## 🟡 Speicherplatz knapp ({free_gb:.1f} GB frei, Schwelle {warn_gb:.0f} GB)", ""]

    verb = "getrimmt" if applied else "WÜRDE trimmen (dry-run)"
    out.append(f"## 🧹 Auto-safe {verb} ({len(trimmed)})")
    out.append("")
    if trimmed:
        for t in sorted(trimmed, key=lambda x: -x.freed_mb):
            out.append(f"- **{t.name}** — {t.freed_mb:.0f} MB frei ({t.method})")
    else:
        out.append("- nichts zu tun")
    out.append("")

    if skipped:
        out.append(f"## ⏭️ Übersprungen ({len(skipped)})")
        out.append("")
        for s in skipped:
            out.append(f"- **{s.name}** — {s.reason}")
        out.append("")

    out.append(f"## 🟠 Verwaiste Kandidaten — bitte manuell prüfen ({len(orphans)})")
    out.append("")
    if orphans:
        for o in sorted(orphans, key=lambda x: -x["size_mb"]):
            out.append(f"- **{o['name']}** ({o['size_mb']:.0f} MB) — {o['reason']}")
    else:
        out.append("- keine")
    out.append("")

    return "\n".join(out)


def notify(trimmed: list[Trimmed], orphans: list[dict], free_gb: float, critical_gb: float, warn_gb: float) -> None:
    freed_total = sum(t.freed_mb for t in trimmed)
    bits = [f"🧹 {freed_total:.0f} MB getrimmt"]
    if orphans:
        bits.append(f"🟠 {len(orphans)} Kandidat(en)")
    if free_gb <= critical_gb:
        bits.append(f"🔴 nur {free_gb:.1f} GB frei")
    elif free_gb <= warn_gb:
        bits.append(f"🟡 {free_gb:.1f} GB frei")
    msg = " · ".join(bits)
    script = f'display notification "{msg}" with title "🧺 Storage Janitor" subtitle "Report aktualisiert"'
    run(["osascript", "-e", script])


def main() -> int:
    ap = argparse.ArgumentParser(description="Storage Janitor")
    ap.add_argument("--dry-run", action="store_true", help="nichts verändern, nur zeigen")
    ap.add_argument("--no-notify", action="store_true", help="keine macOS-Notification")
    args = ap.parse_args()
    apply = not args.dry_run

    rules = load_rules()
    if not rules:
        print(f"Keine Regeln geladen ({RULES_FILE}) — cp rules.example.json rules.json", file=sys.stderr)
        return 1

    trimmed: list[Trimmed] = []
    skipped: list[Skipped] = []
    known_names: set[str] = set()

    for entry in rules.get("regenerable_caches", []):
        known_names.add(entry.get("path", entry["name"]))
        t, s = trim_regenerable(entry, apply)
        if t:
            trimmed.append(t)
        if s:
            skipped.append(s)

    for entry in rules.get("capped_app_caches", []):
        known_names.add(entry.get("path", entry["name"]))
        t, s = trim_capped(entry, apply)
        if t:
            trimmed.append(t)
        if s:
            skipped.append(s)

    orphan_cfg = rules.get("orphan_scan", {})
    known_names |= set(orphan_cfg.get("ignore", []))
    orphans = find_orphan_candidates(known_names, min_mb=float(orphan_cfg.get("min_size_mb", 5)))

    thresholds = rules.get("disk_space_thresholds", {})
    warn_gb = float(thresholds.get("warn_gb", 20))
    critical_gb = float(thresholds.get("critical_gb", 8))
    total_gb, free_gb = disk_space()

    REPORTS.mkdir(parents=True, exist_ok=True)
    report = build_report(trimmed, skipped, orphans, total_gb, free_gb, warn_gb, critical_gb, applied=apply)
    stamp = datetime.now().strftime("%Y-%m-%d")
    (REPORTS / f"{stamp}.md").write_text(report, encoding="utf-8")
    (REPORTS / "latest.md").write_text(report, encoding="utf-8")

    state = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "applied": apply,
        "disk_total_gb": round(total_gb, 1),
        "disk_free_gb": round(free_gb, 1),
        "warn_gb": warn_gb,
        "critical_gb": critical_gb,
        "summary": {
            "trimmed": len(trimmed),
            "skipped": len(skipped),
            "orphan_candidates": len(orphans),
            "freed_mb": round(sum(t.freed_mb for t in trimmed), 1),
        },
        "trimmed": [asdict(t) for t in trimmed],
        "skipped": [asdict(s) for s in skipped],
        "orphan_candidates": orphans,
    }
    (SELF_DIR / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_notify:
        notify(trimmed, orphans, free_gb, critical_gb, warn_gb)

    print(report)
    print(f"\n→ Report: {REPORTS / 'latest.md'}  ·  state.json geschrieben"
          f"  ·  {'angewendet' if apply else 'NICHT angewendet (dry-run)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
