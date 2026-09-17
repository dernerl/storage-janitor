#!/bin/zsh
# Dünner Wrapper (v.a. für launchd): launchd startet mit minimalem PATH, daher hier setzen,
# damit python3 / brew / pip3 / pnpm / go / mdfind / osascript gefunden werden.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "${0:A:h}" || exit 1
exec python3 storage-janitor.py "$@" >> reports/run.log 2>&1
