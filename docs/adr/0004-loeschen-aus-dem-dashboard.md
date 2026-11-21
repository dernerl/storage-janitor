# 4. Löschen aus dem Dashboard (Kontextmenü)

Date: 2026-10-13

## Status

Accepted

## Context

Das Dashboard zeigt, wo der Platz liegt, aber zum Aufräumen musste man jedes Mal in den
Finder. Gewünscht war ein Rechtsklick-Menü auf den Kacheln, mit dem man direkt löschen kann.
Der Server läuft nur auf 127.0.0.1, die Pfade kommen aber vom Browser. Ein Fehler (oder eine
fremde Seite) darf darüber nicht `~`, `/System` oder ein Programm-Bundle von innen zerlegen.

## Decision

- **Zwei Wege:** „In den Papierkorb legen“ über `/usr/bin/trash` (ab macOS 15). Das setzt die
  Zurücklegen-Daten wie der Finder und braucht keine Automation-Freigabe für den Finder. Dazu
  „Endgültig löschen“ (`shutil.rmtree`/`os.remove`) mit eigener, roter Warnung. Der Fokus steht
  dort auf „Abbrechen“.
- **Whitelist im Server** (`deletable()`, im Frontend gespiegelt, nur um Einträge auszugrauen):
  im Home ab zwei Ebenen (also nicht `~/Library` oder `~/Documents` selbst) und `.app`-Bundles
  unter `/Applications`, die nicht in einer anderen `.app` stecken (z. B. `KiCad/KiCad.app`).
  System, `/private`, `/opt` und `/usr` bleiben gesperrt.
- **Pfadprüfung:** erst `normpath` (sonst ginge `~/a/..` als Pfad unter `~/a` durch), dann
  `realpath` nur für den Elternordner. Ein Symlink wird also selbst gelöscht, nicht sein Ziel.
  Origin-Check wie bei den übrigen POSTs.
- **Kein Rescan nach dem Löschen:** Das Frontend nimmt den Knoten aus dem Baum und zieht die
  Größen von den Vorfahren ab. Beim Papierkorb wandert die Größe nach `~/.Trash` (gleiches
  Volume, noch nicht frei), beim endgültigen Löschen wird sie frei.
- Eigene Dialoge im 95er-Stil statt `confirm()`: Browser-Dialoge blockieren und passen nicht
  zum Stil.

## Consequences

- Aufräumen geht direkt aus der Karte. Die Größe steht im Bestätigungsdialog.
- Root-eigene Programme lassen sich nicht in den Papierkorb legen, weil der Server als User
  läuft. Der Fehler kommt als Dialog. Das ist gewollt: Das Dashboard bekommt keine Root-Rechte
  zum Löschen.
- Nach vielen Löschungen ist die Karte nur noch eine Näherung (Sammelposten wie „(N kleinere
  Ordner)“ werden nicht neu berechnet). Der nächste Scan gleicht das wieder ab.
