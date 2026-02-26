#!/usr/bin/env bash
set -euo pipefail

# Run the Flask server with the project's venv if available.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
fi

export PORT=${PORT:-7700}
export FLASK_DEBUG=${FLASK_DEBUG:-1}

python "$ROOT_DIR/app.py"
