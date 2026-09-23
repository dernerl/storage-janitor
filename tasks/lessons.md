# Lessons

## `--force` bei Cache-Tools nie gegen laufende Prozesse (2026-09-23)
- `uv cache prune --force` hat die `archive-v0`-Umgebung eines laufenden `uvx`-MCP-Servers
  gelöscht — Annahme „laufende Envs sind unabhängige APFS-Clones“ war falsch, uvx läuft direkt
  aus dem Cache.
- Regel: Lock-/In-use-Checks eines Tools nie per `--force` umgehen. Vorher prüfen, *woraus*
  laufende Prozesse ausgeführt werden (`ps -o command`), und im Zweifel den Lauf überspringen.
