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
