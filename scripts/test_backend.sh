#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "error: ${PYTHON_BIN} not found. Run ./scripts/bootstrap_backend_env.sh first." >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  exec "${PYTHON_BIN}" -m pytest tests -q
fi

exec "${PYTHON_BIN}" -m pytest "$@"
