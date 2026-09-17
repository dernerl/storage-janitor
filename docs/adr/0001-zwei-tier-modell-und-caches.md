# 1. Zwei-Tier-Modell: auto-safe vs. recommend-only

Date: 2026-09-17

## Status

Accepted

## Context

`~/Library/Caches` wuchs unbemerkt auf 16 GB, während der freie Speicherplatz auf 6,1 GB
gefallen war. Die Bestandteile fielen in drei klar unterscheidbare Kategorien:

- Reine Rebuild-/Download-Caches von Dev-Tools (Homebrew, pip, pnpm, go-build, Playwright-
  Binaries, …) — Verlust ist folgenlos, alles regeneriert sich beim nächsten Bedarf.
- Browser-Caches (Chrome/Edge/Brave), die unbegrenzt wachsen. Für sie gibt es *keinen*
  zuverlässigen "Ursache abstellen"-Schalter: die kursierende `defaults write DiskCacheSize`-
  Anleitung setzt nur "Recommended"-Policy-Level, Chromiums eigene `DiskCacheSize`-Policy
  verlangt aber "Mandatory" — wird also ignoriert. Der "echte" Mandatory-Weg über
  `/Library/Managed Preferences/` ist auf aktuellem macOS ohne MDM nachweislich
  unzuverlässig. Der einzig robuste Hebel ist regelmäßiges Trimmen.
- Verwaiste Reste von deinstallierten Tools/archivierten Projekten (heute gefunden:
  `ollama`-Cache nach Deinstallation, `complisec`-Cache nach vollständigem Rückbau des
  Projekts) — hier lässt sich "wirklich weg" nicht rein mechanisch beweisen, das erfordert
  Kontext, den ein Script nicht sicher hat.

Das bestehende Schwester-Tool `workbench-janitor` ist strikt recommend-only ("empfiehlt nur,
löscht nie selbst") — das passt für Projekt-Ordner, wo jede Löschung potenziell Arbeit
vernichtet. Für System-Caches gilt das nur für einen Teil der Fälle; ein Tool, das *nie*
etwas anfasst, würde das ursprüngliche Problem (unbemerktes Wachstum) nicht lösen.

## Decision

**Zwei Tiers, klar getrennt:**

- **auto-safe** — wird bei jedem Lauf automatisch angewendet, ohne `--apply`-Flag:
  - `regenerable_caches`: reine Tool-Caches, per Konfiguration gelistet, mit dediziertem
    Cleanup-Kommando wo verfügbar (`brew cleanup -s`, `pip3 cache purge`, `pnpm store prune`,
    `go clean -cache`), sonst `rm -rf` auf das Cache-Verzeichnis selbst.
  - `capped_app_caches`: Browser-Caches, getrimmt nur wenn sie ein konfiguriertes
    `max_size_mb`-Limit überschreiten (kein sinnloses wöchentliches Voll-Wipe). **Sicherheits-
    Check zuerst:** läuft der zugehörige Prozess (`pgrep`), wird der Lauf für diesen Eintrag
    übersprungen und im Report vermerkt — nie eine App-Cache-Struktur unter laufendem Prozess
    wegreißen.
- **recommend-only** — wird nur gemeldet, nie automatisch verändert:
  - Verwaiste Cache-Kandidaten: dynamische Heuristik (Bundle-ID-förmiger Name ohne
    Treffer unter installierten Apps via `mdfind`/`mdls`, oder einfacher Tool-Name ohne
    Treffer via `command -v`). System-eigene `com.apple.*`-Caches werden nie geprüft.
  - Speicherplatz-Schwelle (`df` auf `/System/Volumes/Data`): Warn-/Kritisch-Meldung, keine
    Aktion — was konkret Platz schafft (große Downloads, doppelte Projektordner, …) erfordert
    menschliches Urteil.

Fremde App-Configs mit Auth-/Session-Daten (z.B. Spotifys `prefs`-Datei) werden nie
automatisch verändert — ein Cache-Ordner löschen ist reversibel (regeneriert sich), eine
Config-Datei mit Login-Tokens zu editieren ist es nicht in derselben Weise.

Ansonsten identisches Fundament wie `workbench-janitor`: deterministischer Python-Kern ohne
LLM, lokale auth-freie Sinks (`state.json` + `reports/latest.md` + macOS-Notification),
Scheduling über `/loop` in der aufrufenden Session statt launchd (siehe `workbench-janitor`
ADR 0001 — Full-Disk-Access-Problem bei geschützten Ordnern gilt hier nicht direkt, da
`~/Library/Caches` nicht TCC-geschützt ist, aber die Konvention wird der Konsistenz halber
übernommen).

## Consequences

- Löst das eigentliche Problem (unbemerktes Wachstum) automatisch, ohne bei jedem Lauf um
  Erlaubnis zu fragen — für den klar abgegrenzten "garantiert regenerierbar"-Fall.
- Bewahrt die "nie ohne Rückfrage löschen"-Garantie für alles mit Urteilsspielraum, konsistent
  mit `workbench-janitor`s Philosophie.
- Die Grenze zwischen den Tiers lebt in `rules.json` (Konfiguration), nicht im Code — neue
  Cache-Quellen lassen sich ohne Codeänderung hinzufügen.
- Bewusst außerhalb von v1: Duplikat-Projektordner-Erkennung (gehört zu `workbench-janitor`s
  Scan-Domäne, die Projektordner bereits kennt) und automatisches Nachziehen fremder App-
  Configs (Spotify-`prefs` bleibt ein einmaliger, manueller Schritt).
