#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -x .venv/bin/python ]]; then
  echo "The application is not set up yet. Run ./setup.sh first." >&2
  exit 1
fi

if [[ ! -f web/dist/index.html ]]; then
  echo "The web interface is not built. Run ./setup.sh first." >&2
  exit 1
fi

URL="http://127.0.0.1:8517"
if command -v xdg-open >/dev/null 2>&1; then
  (sleep 1; xdg-open "$URL" >/dev/null 2>&1 || true) &
fi

exec ./.venv/bin/python scripts/run_playground_app.py
