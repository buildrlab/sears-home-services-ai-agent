#!/usr/bin/env bash

set -Eeuo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

SKIP_DOCKER_BUILD=0

usage() {
  cat <<'USAGE'
Usage: scripts/local/test-backend.sh [--skip-docker-build]

Matches Backend CI:
- installs backend dev tooling
- runs Ruff
- runs pytest with warnings as errors
- runs pip-audit
- builds the backend Docker image unless --skip-docker-build is used
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-docker-build)
      SKIP_DOCKER_BUILD=1
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

ensure_backend_tooling
python_bin="$(backend_python)"
(cd "${REPO_ROOT}/backend" && "${python_bin}" -m ruff check .)
(cd "${REPO_ROOT}/backend" && "${python_bin}" -W error -m pytest)
(cd "${REPO_ROOT}/backend" && "${python_bin}" -m pip_audit)

if [ "${SKIP_DOCKER_BUILD}" -ne 1 ]; then
  require_command docker
  docker build -t shs-ai-agent-backend:local-ci "${REPO_ROOT}/backend"
fi
