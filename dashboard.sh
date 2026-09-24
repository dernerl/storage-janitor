#!/bin/zsh
# Start/Stop-Wrapper für das Localhost-Dashboard (dashboard/index.html + dashboard/server.py).
# Muster wie workbench-janitor/dashboard.sh, aber mit eigenem Server (Scan-Button, Finder).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "${0:A:h}" || exit 1

export STORAGE_DASHBOARD_PORT="${STORAGE_DASHBOARD_PORT:-8935}"
PIDFILE=".dashboard.pid"
URL="http://localhost:$STORAGE_DASHBOARD_PORT/"

is_running() {
    [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

start() {
    if is_running; then
        return 0
    fi
    nohup python3 dashboard/server.py >/dev/null 2>&1 &
    echo $! > "$PIDFILE"
    disown
    # Ohne Scan hätte das Dashboard nichts anzuzeigen — dann direkt einen im Hintergrund starten
    [[ -f scans/latest.json ]] || python3 disk-scan.py --background
    sleep 0.3
}

stop() {
    if is_running; then
        kill "$(cat "$PIDFILE")" 2>/dev/null
    fi
    rm -f "$PIDFILE"
}

status() {
    if is_running; then
        echo "läuft (PID $(cat "$PIDFILE")) — $URL"
    else
        echo "gestoppt"
    fi
}

case "$1" in
    start)  start; echo "$URL" ;;
    stop)   stop ;;
    status) status ;;
    open)   start; open "$URL${2:-}" ;;     # $2 optional: "#%2FUsers%2Fhug" oder "?tab=growth"
    scan)   python3 disk-scan.py --background ;;
    *) echo "Usage: $0 {start|stop|status|open [suffix]|scan}"; exit 1 ;;
esac
