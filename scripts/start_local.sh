#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'Create .venv and install requirements.txt first (see docs/UPGRADE.md).'
  exit 1
fi
AQUA_LOCAL_PORT="$(.venv/bin/python -c 'import app, os; print(os.getenv("PORT", "8081"))')"
echo "AquaSustain agent workspace v0.4.0 — Web Preview port $AQUA_LOCAL_PORT"
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "$AQUA_LOCAL_PORT"
