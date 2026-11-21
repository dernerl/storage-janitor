# Treemap-Dashboard (à la WinDirStat/TreeSize)

Plan: ~/.claude/plans/luminous-sleeping-cherny.md · Entscheidungen: ganze Platte mit sudo,
Scan per Button + täglich, Wachstum anzeigen.

- [x] `disk-scan.py` — Walk Data-Volume, sudo via `sudo -n` + stdout-Übergabe, Pruning, Kategorien
- [x] Wachstum: `d`-Delta pro Knoten + `growth.json` (gewachsen/geschrumpft)
- [x] `dashboard/server.py` — Static + `/api/status`, `/api/scan`, `/api/reveal`, Origin-Check
- [x] `dashboard.sh` — start/stop/status/open (Muster workbench-janitor)
- [x] `dashboard/index.html` — Canvas-Treemap, Drilldown, Metrik-Umschalter, Seitenleiste
- [x] SwiftBar: Dashboard/Scan-Menüpunkte, Top-Ordner, täglicher Hintergrund-Scan
- [x] ADR 0003, README, .gitignore
- [x] Verifikation (Scanner, Wachstum, Server, UI headless Chrome, SwiftBar-Output)
- [ ] sudo-Vollscan verifizieren — braucht `sudo -v` des Users im echten Terminal

## Review

- Scanner: 1,88 Mio. Dateien, 146 GB erfasst, ~52 s, 0,61 MB JSON, ~9000 Knoten; Werte pro
  Home-Unterordner stimmen mit `du` überein.
- Wachstum: 500-MB-Testdatei erscheint als einziger Eintrag (+524 MB), ohne Vorfahren-Kette.
- Server: Traversal → 404, POST ohne/fremder Origin → 403, zweiter Scan-Klick startet keinen
  zweiten Scan, `reveal` außerhalb des Scan-Roots → 404, gültiger Pfad → Finder.
- UI: Headless-Chrome-Screenshots hell/dunkel, Drilldown per Hash, Wachstums-Ansicht, 600 px.
  claude-in-chrome war nicht verbunden → Hover/Klick nicht interaktiv getestet.
- Gefundene Fehler unterwegs: erster Scan zeigte alles als „gewachsen“; `.dmg` im System als
  Dokument; `/System/Volumes/Data/System` als Sonstiges; SwiftBar-„Größte Ordner“ zu tief.

### Nachtrag 2026-09-24 — Vaporwave als Standard, Klick → Finder
- Vaporwave-Skin ist jetzt `dashboard/index.html`; Apple-Stil, Phosphor und Tron entfernt
  (Backup nur im Session-Scratchpad), `themes/`-Route im Server wieder entfernt.
- Bug gefunden per echtem Klicktest (CDP): `.empty` mit `hidden`-Attribut lag wegen
  `display:flex` unsichtbar über der Karte und schluckte alle Klicks/Hover — schon seit der
  ersten Version. Fix: `.empty[hidden] { display: none; }`.
- Klickverhalten: Einfachklick zoomt, Doppelklick/⌘-Klick → Finder; 6/6 Fälle mit echten
  Maus-Events verifiziert (Finder-Aufrufe im Test abgefangen).

# Kontextmenü auf Kacheln + Startmenü „Plaza“ (2026-10-13)

## Kontextmenü (Rechtsklick auf Kachel, Win95-Stil)
- [x] Menü: **Öffnen** (nur Ordner, = Drilldown) · **Im Finder zeigen** · **Pfad kopieren** ·
      ─ · **In den Papierkorb legen…** · ─ · **Eigenschaften** (Größe, Dateien, Wachstum, Pfad)
- [x] Ausgegraut bei schraffierten Blöcken / Sammelposten „(N kleinere…)“ / geschützten Pfaden
- [x] Löschen: **In den Papierkorb legen…** (Finder, „Zurücklegen“ geht) und **Endgültig löschen…**
      (zweite, deutliche Warnung). Bestätigung in eigenem Win95-Dialog (kein `confirm()`)
- [x] Server `/api/trash`: Origin-Check wie bisher, `realpath`, nur erlaubte Bereiche:
      unter `$HOME` mit mind. 2 Ebenen Tiefe (nicht `~/Library`, `~/Documents` selbst),
      `.app` unter `/Applications`, nicht in einer anderen `.app` (auch `KiCad/KiCad.app`) — System, /private, /opt bleiben gesperrt (Entscheidung User)
- [x] Nach Erfolg: Knoten lokal aus dem Baum nehmen, Größen der Vorfahren abziehen, neu zeichnen
      (kein Rescan nötig), Ticker-Meldung „🗑 x GB in den Papierkorb“
- [x] Tastatur/Esc schließt Menü, Klick daneben schließt, Menü bleibt im Viewport

## Startmenü „Plaza“ (Taskleiste unten links)
- [x] Win95/98-Startmenü: senkrechter Banner „Plaza Data-Volume“ links, Einträge rechts
- [x] Einträge: **Jetzt scannen** · **Erdgeschoss** (zur Wurzel) · **Ansicht ▸** Größe/Dateien/Wachstum ·
      ─ · **Papierkorb öffnen** · **macOS-Speicherverwaltung** · ─ · **Über Plaza…** (Scan-Infos)
- [x] „Jetzt scannen“ zusätzlich behalten im Header (zeigt Fortschritt) — Startmenü ist Zweitweg
- [x] Server: `/api/open` mit fester Whitelist (Papierkorb, Speicher-Einstellungen), keine freien Pfade

## Verifikation
- [x] `py_compile` + curl: `/api/trash` ohne Origin 403, außerhalb Whitelist 403, Testdatei → Papierkorb
- [x] Echte Maus-Events (CDP): Rechtsklick öffnet Menü, Esc/Klick daneben schließt, Startmenü
- [x] Löschen einer Testdatei Ende-zu-Ende inkl. „Zurücklegen“ im Finder möglich

## Review
- Papierkorb über `/usr/bin/trash -s` statt Finder-AppleScript, also ohne Automation-Freigabe.
  Die Zurücklegen-Daten (`ptbL`/`ptbN` in `~/.Trash/.DS_Store`) werden gesetzt.
- Server (11 Fälle): ohne Origin → 403. `~`, `~/Library`, `~/Library/..`, relativer Pfad,
  `/private/var/tmp` und `.app` in `.app` → 403. Fehlender Pfad → 404, Papierkorb und
  endgültig → 200. `/api/open` mit freiem Ziel → 404.
- UI per CDP mit echten Maus- und Tastatur-Events: 21/21 grün. Geprüft: Rechtsklick, Esc,
  Papierkorb bis auf die Platte, Abbrechen per Enter, endgültig löschen, gesperrte und
  virtuelle Kacheln, Eigenschaften, Klick daneben ohne Zoom, Startmenü über der Taskleiste,
  Untermenü per Hover, Metrikwechsel, Toggle, Über-Dialog.
- Unterwegs gefunden: `~/a/..` wäre ohne `normpath` als Pfad unter `~/a` durchgegangen und
  hätte damit das Home-Verzeichnis getroffen.
- Rechtsklick gilt, wie Tooltip und Doppelklick, immer der tiefsten Kachel unter der Maus.

### Nachtrag — Knöpfe in den Kopf- und Toolbar-Bereich entfernt (Wunsch User)
- [x] „Jetzt scannen“ (Kopf) und die Leiste „Fläche nach“ entfernt; beides nur noch im Startmenü
- [x] Zustand in Variablen statt im DOM (`scanning`, `sudoTicket`, `setMetric()`); der
      sudo-Hinweis steht jetzt als Tooltip am Startmenü-Eintrag
- [x] Aktive Metrik steht im Kartentitel, wenn sie nicht „Größe“ ist; `?metric=` geht weiter
- [x] UI-Test 24/24 grün (inkl. Knöpfe weg, Titel zeigt Metrik)

# Chronik-Ansicht: Historie des Speicherzuwachses (2026-10-13)

- [x] `disk-scan.py`: `scans/history.jsonl` — eine Zeile pro Scan (Zeit, root?, Volume, Kategorie-
      Summen, Ordner ≥ 100 MB bis Tiefe 6 in MB), nie rotiert; fehlende Scans aus der Rotation
      nachholen (Backfill), `--history` zum Nachholen ohne Scan
- [x] `server.py`: `/api/history` = history.jsonl + Tageswerte „Freier Speicher“ aus `reports/*.md`
- [x] Ansicht „Chronik“ (Startmenü, `#chronik`), ersetzt Toolbar/Lageplan/Wegweiser/Legende
  - [x] Zeitraum 7 Tage / 30 Tage / Alles + Kennzahl (Belegt jetzt, Δ im Zeitraum, Ø pro Tag)
  - [x] Linie „Belegt“ (Tageswerte Janitor) + Scan-Punkte (gefüllt = root, hohl = ohne sudo), Crosshair-Tooltip
  - [x] Gestapelte Flächen je Kategorie pro Scan, Reihenfolge CVD-validiert (ΔE ≥ 19,7),
        Nicht erfasst/macOS schraffiert oben, Legende, Crosshair-Tooltip
  - [x] Liste „Größte Veränderungen“ (gleiche Rechte an beiden Enden bevorzugt, Vorfahren-Filter
        wie growth.json, ab 200 MB), Sparkline, Klick → Lageplan an der Stelle
- [x] Verifikation: Backfill aus 14 Scans, `/api/history`, CDP-Test (Startmenü → Chronik, Zeitraum,
      Hover-Tooltip, Klick in Liste → Lageplan, zurück), Screenshot hell genug/keine Überlappung

## Review
- `history.jsonl`: 14 Scans per Backfill übernommen (~33 KB pro Scan); ein zweiter Lauf trägt
  nichts doppelt ein. Pro Zeile auch die Zahl gesperrter Ordner (`locked`).
- Vergleichbarkeit: Gleiche Rechte reichen nicht. Der Scan von 09:39 (mit Festplattenvollzugriff,
  196 gesperrt) gegen ältere Scans (500 gesperrt) hätte `~` mit +17 GB als „gewachsen“ gezeigt.
  Deshalb wird nur bei gleichen Rechten und höchstens 50 Ordnern Unterschied verglichen, sonst
  erscheint eine Warnung.
- Daten-Auffälligkeit: Am 02.–05.10. zählt der Baum bis zu 54 GB mehr als das Volume
  (85 GB in `/private/var/folders/…/X`, vermutlich APFS-Klone). Wird im Chart mit „!“ markiert,
  nicht versteckt.
- Farbe: Das Kategorie-Schema der App fällt im Validator durch (Neon-Pastelle, zu hell). Die
  Stapelreihenfolge ist so gewählt, dass benachbarte Paare ΔE ≥ 19,7 haben (CVD). Dazu Legende,
  Tooltip mit Werten und Schraffur für die nicht begehbaren Bereiche.
- CDP-Test 16/16 grün (Startmenü → Chronik, Kennzahlen, Hover in beiden Charts, Zeitraum, Klick →
  Lageplan, Browser-Zurück, Lageplan per Startmenü, keine JS-Fehler, 420 px ohne Querscrollen).
  Kontextmenü-Test weiter 24/24.
- Bug gefunden: Der ResizeObserver hat die ausgeblendete Karte mit Breite 0 gezeichnet
  (`drawImage`-Fehler). Fix: `draw()` bricht bei 0 × 0 ab.
