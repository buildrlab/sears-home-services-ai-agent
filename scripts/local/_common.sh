#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-shs-ai-agent-local}"
COMPOSE_FILES=(
  -f "${REPO_ROOT}/docker-compose.yml"
  -f "${REPO_ROOT}/docker-compose.local.yml"
)

compose() {
  docker compose -p "${COMPOSE_PROJECT_NAME}" "${COMPOSE_FILES[@]}" "$@"
}

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Missing required command: ${command_name}" >&2
    exit 127
  fi
}

backend_python() {
  if [ -x "${REPO_ROOT}/backend/.venv/bin/python" ]; then
    printf '%s\n' "${REPO_ROOT}/backend/.venv/bin/python"
    return
  fi
  printf '%s\n' "${PYTHON_BIN:-python3.14}"
}

ensure_backend_tooling() {
  local python_bin
  python_bin="$(backend_python)"
  (cd "${REPO_ROOT}/backend" && "${python_bin}" -m pip install --upgrade pip)
  (cd "${REPO_ROOT}/backend" && "${python_bin}" -m pip install -e ".[dev]")
}

ensure_pnpm() {
  require_command corepack
  corepack enable
  corepack prepare pnpm@11.9.0 --activate
}
