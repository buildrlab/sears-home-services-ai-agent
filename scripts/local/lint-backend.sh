#!/usr/bin/env bash

set -Eeuo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
  cat <<'USAGE'
Usage: scripts/local/lint-backend.sh

Matches Backend CI lint setup:
- installs backend dev tooling
- runs Ruff from backend/
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

ensure_backend_tooling
python_bin="$(backend_python)"
(cd "${REPO_ROOT}/backend" && "${python_bin}" -m ruff check .)
