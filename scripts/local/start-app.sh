#!/usr/bin/env bash

set -Eeuo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

WITH_FRONTEND=1
WITH_BUILD=1

usage() {
  cat <<'USAGE'
Usage: scripts/local/start-app.sh [--no-frontend] [--no-build]

Starts the local SHS application with Docker Compose:
- PostgreSQL 18
- Mailpit
- MinIO
- backend migration/seed one-off task
- FastAPI backend on http://127.0.0.1:8000
- React frontend on http://127.0.0.1:5173 unless --no-frontend is used

The script creates the local MinIO upload bucket if needed.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-frontend)
      WITH_FRONTEND=0
      ;;
    --no-build)
      WITH_BUILD=0
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

require_command docker

if [ "${WITH_BUILD}" -eq 1 ]; then
  compose up -d --build postgres mailpit minio
  compose build backend
else
  compose up -d postgres mailpit minio
done

compose run --rm --entrypoint python backend -c '
import time

import boto3
from botocore.exceptions import ClientError

bucket = "shs-ai-agent-uploads-local"
s3 = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
    region_name="us-east-1",
)
for attempt in range(30):
    try:
        s3.create_bucket(Bucket=bucket)
        print(f"Created MinIO bucket: {bucket}")
        break
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            print(f"MinIO bucket already exists: {bucket}")
            break
        if attempt == 29:
            raise
    except Exception:
        if attempt == 29:
            raise
    time.sleep(2)
'

compose run --rm backend-migrate

services=(backend)
if [ "${WITH_FRONTEND}" -eq 1 ]; then
  services+=(frontend)
fi

if [ "${WITH_BUILD}" -eq 1 ]; then
  compose up -d --build "${services[@]}"
else
  compose up -d "${services[@]}"
fi

compose ps

cat <<'SUMMARY'

Local app is starting:
- API: http://127.0.0.1:8000/healthz
- Frontend: http://127.0.0.1:5173
- Mailpit: http://127.0.0.1:8025
- MinIO console: http://127.0.0.1:9001

Run:
  scripts/local/smoke-local.sh
SUMMARY
