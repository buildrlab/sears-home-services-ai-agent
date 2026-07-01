# Local Testing Runbook

This runbook must stay simple and current. If a command changes, update this file in the same pull request.

## Prerequisites

- Docker Desktop or compatible Docker runtime.
- Python 3.14.
- Node.js 26.4.0 or newer.
- pnpm 11.9.0 or newer.
- No production secrets in local files.

## Start Local Dependencies

```bash
docker compose up -d postgres mailpit minio
```

Local services:

- PostgreSQL: `localhost:5432`
- Mailpit SMTP: `localhost:1025`
- Mailpit UI: `http://localhost:8025`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`

## Backend Checks

```bash
cd backend
cp .env.example .env
python3.14 -m pip install -e ".[dev]"
python -W error -m pytest
ruff check .
pip-audit
```

Phase 1 and later must also include:

```bash
alembic upgrade head
python -m app.seed
uvicorn app.main:app --port 8000
curl http://127.0.0.1:8000/healthz
```

Phase 2 and later must also verify the scheduling API:

```bash
curl "http://127.0.0.1:8000/scheduling/matches?zip_code=75201&appliance_type=refrigerator"

curl -X POST http://127.0.0.1:8000/appointments/holds \
  -H "Content-Type: application/json" \
  -d '{
    "customer": {
      "full_name": "Jordan Customer",
      "email": "jordan.customer@example.test",
      "phone": "+15551234567"
    },
    "technician_id": 1,
    "appliance_type": "refrigerator",
    "zip_code": "75201",
    "scheduled_start": "2026-07-06T08:00:00+00:00",
    "issue_summary": "Refrigerator is not cooling."
  }'

curl -X POST http://127.0.0.1:8000/appointments/1/book
curl http://127.0.0.1:8000/appointments/1
```

Repeat the hold request for the same technician and `scheduled_start` with a
different customer. The expected response is HTTP `409 Conflict`.

Phase 3 and later must also verify the deterministic diagnostic API. This path
does not require an OpenAI key:

```bash
curl -X POST http://127.0.0.1:8000/diagnostics/sessions \
  -H "Content-Type: application/json" \
  -d '{"customer_phone":"+15551234567"}'

curl -X POST http://127.0.0.1:8000/diagnostics/sessions/1/turn \
  -H "Content-Type: application/json" \
  -d '{"message":"My refrigerator is not cooling and leaking."}'

curl -X POST http://127.0.0.1:8000/diagnostics/sessions/1/turn \
  -H "Content-Type: application/json" \
  -d '{"message":"It is in 75201."}'

curl -X POST http://127.0.0.1:8000/diagnostics/sessions \
  -H "Content-Type: application/json" \
  -d '{}'

curl -X POST http://127.0.0.1:8000/diagnostics/sessions/2/turn \
  -H "Content-Type: application/json" \
  -d '{"message":"The oven has a gas smell and I want to fix the gas line myself."}'
```

The expected result is a `ready_to_schedule` diagnostic session with a
`find_technician_matches` tool call for the normal flow, and a
`safety_escalated` session for the unsafe gas prompt.

Phase 4 and later must also verify the Twilio Gather fallback path locally. In
local/test mode, request validation is skipped when no `TWILIO_AUTH_TOKEN` is
configured:

```bash
curl -X POST http://127.0.0.1:8000/twilio/voice/incoming \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "CallSid=CALOCAL123&From=%2B15551234567&To=%2B17373559397"

curl -X POST http://127.0.0.1:8000/twilio/voice/gather \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "CallSid=CALOCAL123&From=%2B15551234567&To=%2B17373559397&SpeechResult=My%20refrigerator%20is%20not%20cooling%20in%2075201"

curl -i -X POST http://127.0.0.1:8000/twilio/voice/status \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "CallSid=CALOCAL123&CallStatus=completed"
```

The expected result is Gather TwiML from the first two calls and HTTP `204 No
Content` from the status callback. Unit tests also cover signed webhooks and the
ConversationRelay WebSocket handler.

Phase 5 and later must also verify the visual diagnosis backend flow. Start
Mailpit and MinIO with Docker Compose, create the local bucket if it does not
exist, and keep the backend configured with the `.env.example` S3/Mailpit values:

```bash
docker compose up -d mailpit minio
```

```bash
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
    if exc.response.get("Error", {}).get("Code") not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
        raise
PY
```

```bash
curl -X POST http://127.0.0.1:8000/diagnostics/sessions/1/upload-link \
  -H "Content-Type: application/json" \
  -d '{"email":"caller@example.test"}'
```

Open Mailpit at `http://127.0.0.1:8025`, confirm the upload-link email arrived,
and copy the final path segment of the upload URL as `<token>`.

```bash
curl -X POST http://127.0.0.1:8000/uploads/<token>/presigned-post \
  -H "Content-Type: application/json" \
  -d '{"filename":"fridge.png","content_type":"image/png","byte_size":512}'

curl -X POST http://127.0.0.1:8000/uploads/<token>/complete \
  -H "Content-Type: application/json" \
  -d '{"filename":"fridge.png","content_type":"image/png","byte_size":512}'

python -m app.workers.vision --upload-id <upload_id>

curl http://127.0.0.1:8000/diagnostics/sessions/1
```

The expected result is an `analyze_image` diagnostic event and an image upload
with status `analyzed`. The backend tests use fake S3/email/queue providers, so
this local smoke is the manual Mailpit/MinIO proof path until frontend Phase 6
wires real browser file upload.

If local port `5432` is already in use, run a temporary PostgreSQL 18 container
on a different port and override `DATABASE_URL`:

```bash
docker run --rm -d --name shs-phase1-postgres \
  -e POSTGRES_DB=shs_ai_agent \
  -e POSTGRES_USER=shs \
  -e POSTGRES_PASSWORD=shs_local_password \
  -p 55432:5432 \
  postgres:18-alpine

export DATABASE_URL="postgresql+psycopg://shs:shs_local_password@localhost:55432/shs_ai_agent"
```

## Script Checks

Twilio scripts do not call Twilio during local unit tests.

```bash
PYTHONPYCACHEPREFIX=/private/tmp/shs-pycache python3.14 -m compileall scripts tests
PYTHONDONTWRITEBYTECODE=1 python3.14 -m unittest discover -s tests
ruff check scripts tests
```

## Twilio Local Call Smoke Test

Before the backend exists, use the standard-library smoke webhook to validate
Twilio routing through a secure tunnel:

```bash
python3.14 scripts/twilio/smoke_server.py --port 8765
```

Then expose `http://127.0.0.1:8765` with ngrok or cloudflared, point the TwiML
App at the tunnel with `scripts/twilio/setup.py`, call the selected Twilio
number, and confirm the smoke server records `voice_incoming`,
`gather_response`, and `status_callback`.

## Frontend Checks

After frontend dependencies are added:

```bash
cd frontend
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

Browser verification must include checking that the Playwright run and browser console show no unexpected errors.

To run the frontend manually:

```bash
cd frontend
pnpm dev
```

Set the backend upload-link base to the frontend route:

```bash
export UPLOAD_LINK_BASE_URL=http://127.0.0.1:5173/uploads
```

If Vite selects a different port, update `UPLOAD_LINK_BASE_URL` and rerun the
upload-link creation request.

## Full Local Smoke Test

When backend and frontend app code exists, the local smoke test must verify:

- Backend health endpoint responds.
- Migrations apply from an empty database.
- Technician seed data exists.
- Diagnostic flow remembers appliance, symptoms, and ZIP code.
- Scheduling flow prevents double-booking.
- Frontend upload page renders.
- Upload token validation works.
- Mailpit receives the upload-link email.
- The email link opens the React upload page at `/uploads/<token>`.
- Image upload writes to local S3 storage.
- The reviewer dashboard shows sessions, appointments, uploads, and diagnostic events.
- Vision worker updates diagnostic state using mock or configured OpenAI provider.

## Cleanup

```bash
docker compose down
```

Use volume removal only when intentionally resetting all local data:

```bash
docker compose down -v
```

## Rule

Do not move to the next implementation phase with failing tests, unresolved console errors, unexplained warnings, or stale instructions.
