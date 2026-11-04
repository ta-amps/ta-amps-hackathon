#!/bin/sh
R="${ERANOS_WORKER:?set ERANOS_WORKER to an Eranos checkout with its .venv}"
cd "$(dirname "$0")"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD:$PWD/.deps:$R" exec "$R/.venv/bin/python" -m pytest -q -p no:cacheprovider tests "$@"
