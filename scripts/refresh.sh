#!/bin/sh
# Refresh one or more Cricsheet datasets and reload the running API.
#
#   scripts/refresh.sh sma ipl        # named datasets
#   scripts/refresh.sh                # defaults below
#
# Safe to re-run: ingest skips matches already in the database by id, so a
# dataset with nothing new costs one download and a directory scan.
set -eu
cd "$(dirname "$0")/.."
PY=.venv/bin/python
API="${STRYK_API:-http://127.0.0.1:8000}"

# ponytail: hardcoded in-season list, swap for a date-aware pick from
# catalog/competitions.json if keeping this current becomes a chore.
[ $# -gt 0 ] || set -- sma ssh bbl wbb
for d in "$@"; do
    echo "== $d"
    "$PY" scripts/fetch_cricsheet.py "$d"
    "$PY" scripts/ingest.py --dataset "$d"
done

curl -fsS -X POST "$API/api/admin/reload" >/dev/null 2>&1 \
    && echo "== API reloaded" \
    || echo "== API not running, skipped reload"
