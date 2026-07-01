#!/usr/bin/env bash

set -Eeuo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
  cat <<'USAGE'
Usage: scripts/local/lint-frontend.sh

Matches Frontend CI lint setup:
- activates pnpm 11.9.0 through corepack
- installs frontend dependencies with the frozen lockfile
- runs pnpm lint from frontend/
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

ensure_pnpm
(cd "${REPO_ROOT}/frontend" && pnpm install --frozen-lockfile)
(cd "${REPO_ROOT}/frontend" && pnpm lint)
