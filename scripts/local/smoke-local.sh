#!/usr/bin/env bash

set -Eeuo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

API_BASE_URL="http://127.0.0.1:8000"
FRONTEND_BASE_URL="http://127.0.0.1:5173"
WITH_FRONTEND=1
JSON_OUTPUT=0
SKIP_OBJECT_UPLOAD=0

usage() {
  cat <<'USAGE'
Usage: scripts/local/smoke-local.sh [--api-base-url URL] [--frontend-base-url URL] [--api-only] [--json] [--skip-object-upload]

Runs the reviewer local smoke test against a running local app.

Defaults:
  API:      http://127.0.0.1:8000
  Frontend: http://127.0.0.1:5173

Options:
  --api-base-url URL        Override the backend URL.
  --frontend-base-url URL   Override the frontend URL.
  --api-only                Skip frontend shell checks.
  --json                    Print JSON output.
  --skip-object-upload      Skip the MinIO/S3 object upload step.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --api-base-url)
      if [ "$#" -lt 2 ]; then
        echo "--api-base-url requires a value." >&2
        exit 2
      fi
      API_BASE_URL="$2"
      shift
      ;;
    --frontend-base-url)
      if [ "$#" -lt 2 ]; then
        echo "--frontend-base-url requires a value." >&2
        exit 2
      fi
      FRONTEND_BASE_URL="$2"
      WITH_FRONTEND=1
      shift
      ;;
    --api-only)
      WITH_FRONTEND=0
      ;;
    --json)
      JSON_OUTPUT=1
      ;;
    --skip-object-upload)
      SKIP_OBJECT_UPLOAD=1
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

python_bin="${PYTHON_BIN:-python3.14}"
args=(
  "${REPO_ROOT}/scripts/reviewer/local_smoke.py"
  --api-base-url "${API_BASE_URL}"
)

if [ "${WITH_FRONTEND}" -eq 1 ]; then
  args+=(--frontend-base-url "${FRONTEND_BASE_URL}")
fi
if [ "${JSON_OUTPUT}" -eq 1 ]; then
  args+=(--json)
fi
if [ "${SKIP_OBJECT_UPLOAD}" -eq 1 ]; then
  args+=(--skip-object-upload)
fi

"${python_bin}" "${args[@]}"
