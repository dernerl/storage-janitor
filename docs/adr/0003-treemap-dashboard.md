# 3. Treemap-Dashboard für die Speicherbelegung (à la WinDirStat/TreeSize)

Date: 2026-09-23

## Status

Accepted

## Context

Der Janitor räumt bekannte Caches auf, beantwortet aber nicht die Frage „wo ist mein Platz
hin?“. Die 26 → 17 GB-Lücke (ADR 0002) ließ sich nur per `du`-Handarbeit finden. Gewünscht:
visuell sehen, wo große *oder viele* Dateien liegen und was seit dem letzten Mal gewachsen
ist — lokal, im Stil des workbench-janitor-Dashboards, erreichbar über SwiftBar.

Messungen: Das Data-Volume hat ~1,9 Mio. Dateien; ein Vollscan dauert ~52 s (User) —
zu lang für einen Seitenaufruf oder einen SwiftBar-Refresh.

## Decision

- **Eigener Scanner `disk-scan.py`** (stdlib) über `/System/Volumes/Data` statt `/`: Das ist
  das Volume, auf dem Nutzerdaten wirklich liegen; über Firmlinks würde `/` Teile doppelt
  zählen. Der Walk bleibt per `st_dev` auf dem Volume, zählt belegte Blöcke (`st_blocks`, wie
  `du`) und Hardlinks einmal.
- **sudo nur via `sudo -n`**: Ist ein Ticket da (User-Setup `!tty_tickets`, 60 min), scannt
  ein root-Kindprozess. Sein JSON geht in einen vom User-Prozess geöffneten File-Descriptor,
  sein Fortschritt über stderr — so gehört nichts in `scans/` root. Ohne Ticket: User-Scan,
  im Dashboard als „🔒 ohne sudo“ markiert. Nie Passwort-Prompt, nie `-S`.
- **Pruning im Scanner, nicht im Browser**: Ein Kind bleibt eigener Knoten, wenn es ≥ 1 %
  seines Parents (Größe *oder* Dateianzahl) und ≥ 10 MB bzw. ≥ 2000 Dateien hat, max. 40 pro
  Ordner; der Rest wird zu „(N weitere · lose Dateien)“. Relativ zum Parent statt zur
  Gesamtgröße, damit auch beim Hineinzoomen Detail bleibt. Ergebnis: ~9000 Knoten, ~0,6 MB.
- **Differenz „nicht erfasst“ sichtbar machen** statt verschweigen: `df used − gescannt`
  (Snapshots, purgeable, nicht lesbare Ordner) und `Container belegt − Data-Volume` (System-
  Volume, VM/Swap, Preboot) erscheinen als schraffierte Blöcke — die Summe passt zur Platte.
- **Wachstum**: Jeder Knoten bekommt ein Delta gegen den vorherigen Scan; `growth.json`
  listet Zu- und Abnahmen ohne Vorfahren, deren Änderung ein einzelnes Kind zu ≥ 80 %
  erklärt. Erster Scan: kein Delta. 14 Scans werden rotiert.
- **Eigener Mini-Server** (`dashboard/server.py`) statt `python3 -m http.server`, weil das
  Dashboard „Jetzt scannen“ und „Im Finder zeigen“ braucht. Bindet an 127.0.0.1, liefert nur
  `index.html` + zwei JSON-Dateien aus, POSTs nur mit eigenem `Origin` (kein Auslösen durch
  fremde Websites), `reveal` nur für existierende Pfade unter dem Scan-Root.
- **Frontend ohne Framework/CDN-Skripte**: Squarified Treemap (Bruls et al.), Canvas, Farben
  nach Kategorie (Caches, Entwicklung, Apps, Medien, Dokumente, System, Sonstiges). Optik:
  „Vaporwave Mall“ — nach Vergleich von vier Varianten (Apple-Stil, Phosphor-Terminal,
  Vaporwave, Tron) gewählt; nur eine Variante bleibt im Repo, damit die Datenlogik nicht
  mehrfach gepflegt werden muss. Einzige externe Ressource: die Schrift VT323 (Google Fonts,
  mit Fallback).
- **Klickverhalten**: Einfachklick zoomt eine Etage tiefer (liegt dort direkt eine Datei →
  Finder); Doppelklick oder ⌘-Klick zeigt exakt die Kachel unter der Maus im Finder. In einer
  Treemap liegt unter jedem Punkt ein Blatt — „Klick auf Blatt = Finder“ würde das Zoomen
  unmöglich machen. Der Einfachklick wartet 250 ms auf einen möglichen Doppelklick.
- **Zeitplan über SwiftBar**: Das bestehende Plugin startet `disk-scan.py --max-age-hours 24
  --background` — höchstens ein Scan pro Tag, nicht blockierend. Kein launchd.

## Consequences

- Ein Klick in der Menüleiste zeigt die konkreten Brocken (Ordner-Ketten werden zur
  sinnvollen Einheit zusammengefasst, z.B. `~/Library/Developer` statt
  `…/Symbols/System/Library/PrivateFrameworks`) und was gewachsen ist.
- **root umgeht TCC nicht**: Ohne Full Disk Access des aufrufenden Prozesses (Terminal bzw.
  SwiftBar) bleiben u.a. Teile von `~/Library/Containers`, Mail, Messages unlesbar und landen
  unter „nicht erfasst“. Der tägliche SwiftBar-Scan hat meist kein sudo-Ticket → User-Scan;
  vollständig wird er nach `sudo -v` im Terminal + „Jetzt scannen“.
- APFS-Clones werden (wie bei `du`) pro Datei voll gezählt — der Scan kann leicht über der
  realen Belegung liegen; „nicht erfasst“ wird dann auf 0 begrenzt.
- Der Scanner ist bewusst recommend-only: Das Dashboard löscht nichts, es zeigt nur und
  öffnet den Finder. Aufräumen bleibt beim Janitor (ADR 0001/0002) oder beim Menschen.
