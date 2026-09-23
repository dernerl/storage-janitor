# 🧺 storage-janitor

**Cache-Wildwuchs auf macOS in Schach halten — automatisch für das Ungefährliche,
nur Empfehlung für den Rest.**

Wenn `~/Library/Caches` unbemerkt auf zweistellige GB-Zahlen wächst (Browser, Dev-Tool-
Downloads, Reste von deinstallierten Tools), räumt `storage-janitor` das regelmäßig auf.
macOS-only.

## Zwei Tiers

| Tier | Beispiele | Verhalten |
|---|---|---|
| 🧹 **auto-safe** | Homebrew/pip/pnpm/go-Caches, Browser-Cache über Größenlimit | wird bei jedem Lauf automatisch getrimmt |
| 🟠 **recommend-only** | verwaiste Cache-Reste, Speicherplatz-Warnschwelle | wird nur gemeldet |

Läuft ein zugehöriger Browser-Prozess gerade, wird sein Cache für diesen Lauf übersprungen
statt unter laufendem Betrieb weggerissen. Fremde App-Configs (z.B. Spotifys `prefs`-Datei
mit Login-Daten) werden nie automatisch angefasst.

Details zur Tier-Aufteilung: `docs/adr/0001-zwei-tier-modell-und-caches.md`.

## Setup

Requirements: macOS, `python3`. Optional je nach `rules.json`: `brew`, `pip3`, `pnpm`, `go`.

```bash
git clone <this repo>
cd storage-janitor
cp rules.example.json rules.json    # anpassen: welche Caches, welche Limits
python3 storage-janitor.py
```

### Options

```bash
python3 storage-janitor.py            # Tiers anwenden + Report + Notification
python3 storage-janitor.py --dry-run  # nichts verändern, nur zeigen
python3 storage-janitor.py --no-notify
```

### Config — `rules.json`

```json
{
  "regenerable_caches": [
    { "name": "Homebrew", "path": "Homebrew", "command": ["brew", "cleanup", "-s"] }
  ],
  "capped_app_caches": [
    { "name": "Chrome", "path": "Google", "process_name": "Google Chrome", "max_size_mb": 1000 }
  ],
  "rotated_dirs": [
    { "name": "Xcode-DeviceSupport", "path": "~/Library/Developer/Xcode/iOS DeviceSupport", "keep": 1, "process_name": "Xcode" }
  ],
  "orphan_scan": { "min_size_mb": 5 },
  "disk_space_thresholds": { "warn_gb": 20, "critical_gb": 8 }
}
```

`path` ist relativ zu `~/Library/Caches`, außer er beginnt mit `/` oder `~` (z.B. `~/.cache/uv`,
`~/.npm/_cacache`). Ohne `command` wird der Ordner direkt mit `rm -rf` geleert (korrekt für reine
Cache-Verzeichnisse ohne eigene Cleanup-API) — das gilt auch für `capped_app_caches`.

`rotated_dirs` behält nur die `keep` neuesten Unterordner (z.B. Xcode `iOS DeviceSupport`: eine
Version pro Gerät reicht). Details: `docs/adr/0002-caches-ausserhalb-library-caches.md`.

Output: `reports/latest.md`, `state.json` (machine-readable), macOS-Notification.

### Scheduling & Menüleiste

Wie bei [workbench-janitor](https://github.com/dernerl/workbench-janitor): Scheduling über
`/loop <interval> /storage-janitor` in einer bereits autorisierten Session, nicht launchd
(`launchd.plist.template` liegt als dokumentierte Fallback-Option bei). Menüleisten-Anzeige
über [swiftbar-plugins](https://github.com/dernerl/swiftbar-plugins) (`storage-janitor.<intervall>.sh`),
das nur `state.json` liest — dieses Repo enthält keinen SwiftBar-Code.

## Caveats

macOS-only. `rm -rf` auf konfigurierte Cache-Pfade ist absichtlich aggressiv — nur Pfade
eintragen, die wirklich reine, regenerierbare Caches sind.
