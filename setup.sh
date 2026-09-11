#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN=python3.11
elif command -v python3.10 >/dev/null 2>&1; then
  PYTHON_BIN=python3.10
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(sys.version_info[:2] not in ((3, 10), (3, 11)))'; then
  PYTHON_BIN=python3
else
  echo "Python 3.10 or 3.11 is required." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js and npm are required to build the web interface." >&2
  echo "On Ubuntu/Debian, install them with: sudo apt install nodejs npm" >&2
  exit 1
fi

echo "Creating the Python virtual environment..."
"$PYTHON_BIN" -m venv .venv

echo "Installing Python dependencies..."
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e .

echo "Building the web interface..."
npm --prefix web ci
npm --prefix web run build

echo
echo "Setup complete. Start the application with: ./start.sh"
