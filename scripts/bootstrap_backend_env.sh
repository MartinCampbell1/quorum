#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${QUORUM_PYTHON_BIN:-python3.13}"
VENV_DIR="${ROOT_DIR}/.venv"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "error: ${PYTHON_BIN} is required. Override with QUORUM_PYTHON_BIN=/path/to/python3.13" >&2
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python "${PYTHON_BIN}" "${VENV_DIR}"
  else
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi
fi

if command -v uv >/dev/null 2>&1; then
  uv pip install --python "${VENV_DIR}/bin/python" -r "${ROOT_DIR}/requirements-dev.txt"
else
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements-dev.txt"
fi

echo "backend environment ready: ${VENV_DIR}"
echo "python: $("${VENV_DIR}/bin/python" --version)"
