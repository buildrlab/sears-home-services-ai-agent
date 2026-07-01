#!/usr/bin/env bash

set -Eeuo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

SKIP_E2E=0

usage() {
  cat <<'USAGE'
Usage: scripts/local/test-frontend.sh [--skip-e2e]

Matches Frontend CI:
- activates pnpm 11.9.0 through corepack
- installs frontend dependencies with the frozen lockfile
- runs lint, typecheck, unit tests, and build
- installs Chromium and runs Playwright unless --skip-e2e is used
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-e2e)
      SKIP_E2E=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

ensure_pnpm
(cd "${REPO_ROOT}/frontend" && pnpm install --frozen-lockfile)
(cd "${REPO_ROOT}/frontend" && pnpm lint)
(cd "${REPO_ROOT}/frontend" && pnpm typecheck)
(cd "${REPO_ROOT}/frontend" && pnpm test)
(cd "${REPO_ROOT}/frontend" && pnpm build)

if [ "${SKIP_E2E}" -ne 1 ]; then
  (cd "${REPO_ROOT}/frontend" && pnpm exec playwright install --with-deps chromium)
  (cd "${REPO_ROOT}/frontend" && pnpm test:e2e)
fi
