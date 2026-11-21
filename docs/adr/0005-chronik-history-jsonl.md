# 5. Chronik über eine eigene, nie rotierte history.jsonl

Date: 2026-10-13

## Status

Accepted

## Context

Die Chronik-Ansicht soll den Speicherzuwachs über Wochen und Monate zeigen. Die vollen Scans
(je ~0,7 MB) werden aber nach 14 Stück rotiert (ADR 0003), reichen also nur rund zwei Wochen
zurück. Der Janitor schreibt pro Tag einen Report mit „Freier Speicher“, das ist dichter, aber
ohne Ordner-Details und nur auf ganze GiB genau (`df -g`).

## Decision

- **`scans/history.jsonl`**: Pro Scan eine schlanke Zeile mit Zeit, Rechten, Zahl gesperrter
  Ordner, Volume-Werten, Kategorie-Summen und Ordnern ab 100 MB bis Tiefe 6 (in MB). Das sind
  ~33 KB pro Scan, und die Datei wird nie rotiert. `disk-scan.py` trägt nach jedem Scan
  fehlende Rotations-Scans nach, damit ist der Backfill idempotent (`--history`).
- **Zwei Quellen in einem Chart**: Die Linie „Belegt“ kommt aus den Janitor-Tagesreports, die
  Punkte aus den Scans. Keine zweite Achse, beide messen dieselbe Größe.
- **Vergleiche nur zwischen vergleichbaren Scans**: gleiche Rechte und höchstens 50 Ordner
  Unterschied bei den gesperrten Ordnern. Sonst würden sudo- und Festplattenvollzugriffs-
  Unterschiede als Wachstum erscheinen. Ist kein vergleichbarer Scan im Zeitraum, wird
  trotzdem verglichen, aber mit sichtbarer Warnung.

## Consequences

- Die Historie wächst ab jetzt lückenlos, etwa 12 MB pro Jahr bei einem Scan pro Tag.
- Ordner unter 100 MB erscheinen nicht in der Veränderungs-Liste. Überschreitet ein Ordner die
  Schwelle, zählt er als „neu“. Deshalb zeigt die Liste erst Änderungen ab 200 MB.
- Scans ohne Root-Rechte bleiben in der Chronik sichtbar (hohle Marker), statt still
  herausgefiltert zu werden.
