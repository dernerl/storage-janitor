# 2. Caches außerhalb von ~/Library/Caches abdecken

Date: 2026-09-23

## Status

Accepted

## Context

Sechs Tage nach v1 war der freie Speicher trotz täglicher Läufe von 26 auf 17 GB gefallen —
der Janitor hat in der Zeit praktisch nichts freigegeben. Ursache: v1 löst jeden `path`
relativ zu `~/Library/Caches` auf (dort nur 6,5 GB), die großen Brocken lagen außerhalb:

- `~/.cache/uv` — 16 GB (882 Archive, fast alles unreferenzierter Altbestand)
- `~/.npm/_cacache` — 8,4 GB
- `~/Library/Developer/Xcode/iOS DeviceSupport` — 17 GB, je ~5,7 GB pro iOS-Version, von
  denen nur die aktuell auf dem Gerät laufende gebraucht wird

Besonderheit uv: dauerlaufende `uvx`-Prozesse (MCP-Server wie `kicad-mcp-pro`) halten den
Cache-Lock permanent **und laufen direkt aus `archive-v0/`**. `uv cache prune --force`
ignoriert den Lock und hat bei der Erstbereinigung die Umgebung des laufenden Servers
gelöscht (der Prozess lief dank geladener Module weiter; `uvx kicad-mcp-pro --help` hat die
Umgebung für den nächsten Start neu installiert).

## Decision

- `path` darf absolut oder `~`-präfixiert sein (beide Tiers); relativ bleibt relativ zu
  `~/Library/Caches` — bestehende Rules unverändert gültig.
- `capped_app_caches` akzeptieren optional ein `command` (Tool-eigene Cleanup-API statt
  `rm -rf`), und `process_name` ist nur noch optional (kein impliziter Default mehr).
- uv: gecappt bei 5 GB mit `uv cache prune` und `UV_LOCK_TIMEOUT=10`, **nie `--force`** —
  hält ein uvx-Server den Lock, schlägt der Lauf fehl und landet unter „Übersprungen“.
- npm: gecappt bei 3 GB mit `npm cache clean --force` (`--force` ist hier nur npms
  Bestätigungs-Flag, keine Lock-Umgehung). `~/.npm/_npx` bleibt unangetastet.
- Neuer auto-safe-Regeltyp `rotated_dirs`: behält die `keep` neuesten Unterordner (mtime),
  übersprungen solange `process_name` läuft. Erster Einsatz: Xcode DeviceSupport, `keep: 1`.

## Consequences

- Erstbereinigung: 17 → 39 GB frei (uv −12,5 GB, npm −8,5 GB, DeviceSupport −11,3 GB).
- uv wird nur getrimmt, wenn gerade kein uvx-Server läuft. Solange kicad-MCP per `uvx`
  dauerhaft läuft, bleibt der uv-Eintrag im Report „übersprungen“. Abhilfe wäre
  `uv tool install kicad-mcp-pro` und die MCP-Config auf das installierte Binary umstellen.
- Ein nach mtime rotierender Ordner kann theoretisch eine gerade *nicht* neueste, aber noch
  genutzte Version treffen (zweites Gerät mit älterem iOS) — dann `keep` erhöhen; Xcode lädt
  die Symbole bei Bedarf ohnehin neu.
