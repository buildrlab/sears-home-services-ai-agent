# Reviewer Scripts

Scripts in this folder are intended for repeatable reviewer or submission
verification. They must be safe to run locally and must not require production
secrets.

## `local_smoke.py`

Runs a local end-to-end smoke flow against a running backend:

- API health.
- Tier 1 deterministic diagnostic flow.
- Tier 2 technician match, appointment hold, and appointment booking.
- Twilio Gather fallback webhook flow.
- Tier 3 upload link, upload token, presigned S3/MinIO POST, upload completion,
  and deterministic image analysis.
- Optional frontend React shell and upload-route checks.

Prerequisites:

```bash
docker compose up -d postgres mailpit minio
```

```bash
cd backend
cp .env.example .env
python3.14 -m pip install -e ".[dev]"
alembic upgrade head
python -m app.seed
uvicorn app.main:app --port 8000
```

Create the local MinIO bucket if it does not exist:

```bash
cd backend
python - <<'PY'
import boto3
from botocore.exceptions import ClientError

s3 = boto3.client(
    "s3",
    endpoint_url="http://127.0.0.1:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
    region_name="us-east-1",
)
try:
    s3.create_bucket(Bucket="shs-ai-agent-uploads-local")
except ClientError as exc:
    if exc.response.get("Error", {}).get("Code") not in {
        "BucketAlreadyOwnedByYou",
        "BucketAlreadyExists",
    }:
        raise
PY
```

Run the smoke flow:

```bash
python3.14 scripts/reviewer/local_smoke.py \
  --api-base-url http://127.0.0.1:8000
```

With frontend shell checks:

```bash
cd frontend
pnpm dev
```

```bash
python3.14 scripts/reviewer/local_smoke.py \
  --api-base-url http://127.0.0.1:8000 \
  --frontend-base-url http://127.0.0.1:5173
```

Use `--skip-object-upload` only when S3/MinIO is deliberately unavailable and
the API-only upload metadata path is being checked.

If local port `5432` is already in use, follow the alternate PostgreSQL port
instructions in `docs/runbooks/local-testing.md` and use the same `DATABASE_URL`
override for Alembic, seeding, and Uvicorn before running this script.
