# Lessons

## `--force` bei Cache-Tools nie gegen laufende Prozesse (2026-09-23)
- `uv cache prune --force` hat die `archive-v0`-Umgebung eines laufenden `uvx`-MCP-Servers
  gelöscht — Annahme „laufende Envs sind unabhängige APFS-Clones“ war falsch, uvx läuft direkt
  aus dem Cache.
- Regel: Lock-/In-use-Checks eines Tools nie per `--force` umgehen. Vorher prüfen, *woraus*
  laufende Prozesse ausgeführt werden (`ps -o command`), und im Zweifel den Lauf überspringen.

## Screenshots beweisen keine Interaktion (2026-09-24)
- Das Dashboard sah in allen Headless-Screenshots korrekt aus, aber ein unsichtbares Overlay
  (`[hidden]` von `display:flex` überschrieben) schluckte seit der ersten Version jeden Klick.
- Regel: Klick-/Hover-Features mit echten Maus-Events testen (Chrome DevTools Protocol:
  `Input.dispatchMouseEvent`), nicht nur per Screenshot. Bei eigenen `display`-Regeln auf
  Elementen mit `hidden` immer `[hidden] { display: none }` mitschreiben.

## Nach Edits an Server-Code sofort kompilieren (2026-09-24)
- Ein Edit, der Zeilen entfernt, hat einen Zeilenumbruch mitgefressen → SyntaxError, der
  Server startete still nicht (`dashboard.sh` leitet nach /dev/null um).
- Regel: nach jedem Edit an Python-Code `python3 -m py_compile` und einen `curl` gegen den
  Server, bevor darauf aufgebaut wird.
