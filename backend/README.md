# Backend

Python backend for the Sears Home Services voice AI appliance diagnostic agent.

## Stack

- Python 3.14
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL 18
- Pytest
- Ruff
- Twilio SDK
- OpenAI SDK
- AWS SDK for Python

## Responsibilities

- Twilio inbound webhook.
- Twilio ConversationRelay WebSocket handler.
- Twilio Gather fallback flow.
- Diagnostic conversation orchestration.
- Technician scheduling.
- Image upload token creation.
- SES email sending.
- S3 upload coordination.
- SQS vision worker.

## Configuration

Runtime configuration is read from environment variables. For local development,
the defaults target the Docker Compose PostgreSQL service:

```text
DATABASE_URL=postgresql+psycopg://shs:shs_local_password@localhost:5432/shs_ai_agent
ENVIRONMENT=local
DATABASE_ECHO=false
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.5
OPENAI_REASONING_EFFORT=low
OPENAI_VERBOSITY=low
OPENAI_VISION_MODEL=gpt-5.5
TWILIO_AUTH_TOKEN=
TWILIO_VALIDATE_REQUESTS=true
TWILIO_VOICE_MODE=gather
TWILIO_CONVERSATION_RELAY_URL=wss://ws.shs.buildrlab.com/twilio/conversation
PUBLIC_BASE_URL=
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,https://shs.buildrlab.com
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
S3_UPLOAD_BUCKET=shs-ai-agent-uploads-local
S3_ENDPOINT_URL=http://127.0.0.1:9000
S3_PRESIGN_EXPIRES_SECONDS=900
UPLOAD_LINK_BASE_URL=http://127.0.0.1:5173/uploads
UPLOAD_TOKEN_TTL_MINUTES=60
UPLOAD_MAX_BYTES=10485760
UPLOAD_ALLOWED_CONTENT_TYPES=image/jpeg,image/png,image/webp
EMAIL_DELIVERY_MODE=smtp
EMAIL_FROM_ADDRESS="Sears Home Services <no-reply@shs.buildrlab.com>"
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SQS_VISION_QUEUE_URL=
VISION_PRESIGNED_GET_EXPIRES_SECONDS=600
```

The `SHS_`-prefixed aliases are also supported:

```text
SHS_DATABASE_URL=
SHS_ENVIRONMENT=
SHS_DATABASE_ECHO=
SHS_OPENAI_API_KEY=
SHS_OPENAI_MODEL=
SHS_OPENAI_REASONING_EFFORT=
SHS_OPENAI_VERBOSITY=
SHS_OPENAI_VISION_MODEL=
SHS_TWILIO_AUTH_TOKEN=
SHS_TWILIO_VALIDATE_REQUESTS=
SHS_TWILIO_VOICE_MODE=
SHS_TWILIO_CONVERSATION_RELAY_URL=
SHS_PUBLIC_BASE_URL=
SHS_CORS_ALLOWED_ORIGINS=
SHS_AWS_REGION=
SHS_AWS_ACCESS_KEY_ID=
SHS_AWS_SECRET_ACCESS_KEY=
SHS_S3_UPLOAD_BUCKET=
SHS_S3_ENDPOINT_URL=
SHS_UPLOAD_LINK_BASE_URL=
SHS_UPLOAD_TOKEN_TTL_MINUTES=
SHS_UPLOAD_MAX_BYTES=
SHS_UPLOAD_ALLOWED_CONTENT_TYPES=
SHS_EMAIL_DELIVERY_MODE=
SHS_EMAIL_FROM_ADDRESS=
SHS_SMTP_HOST=
SHS_SMTP_PORT=
SHS_SQS_VISION_QUEUE_URL=
```

When no OpenAI API key is configured, the diagnostic agent uses the deterministic
local provider for repeatable local development and tests.

When no OpenAI API key is configured, image analysis also uses the deterministic
local provider. For local email, `EMAIL_DELIVERY_MODE=smtp` sends upload links
to Mailpit. In AWS, set `EMAIL_DELIVERY_MODE=ses` and provide SES/DNS
configuration through Terraform and AWS Secrets Manager.

For Twilio webhooks, keep request validation enabled outside local/test
development and set `TWILIO_AUTH_TOKEN` to the real account auth token through a
secret manager or local uncommitted `.env`. If a tunnel or reverse proxy changes
the externally visible host, set `PUBLIC_BASE_URL` to the HTTPS URL Twilio calls
so signature validation uses the same URL Twilio signed.

`CORS_ALLOWED_ORIGINS` is a comma-separated browser allowlist. Keep it strict in
AWS: `https://shs.buildrlab.com` should be the only browser origin unless a
temporary review environment is explicitly added.

## Local Run

Install dependencies:

```bash
python3.14 -m pip install -e ".[dev]"
```

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Apply migrations and seed local technician reference data:

```bash
cd backend
alembic upgrade head
python -m app.seed
```

Run the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/healthz
```

Find matching technicians:

```bash
curl "http://127.0.0.1:8000/scheduling/matches?zip_code=75201&appliance_type=refrigerator"
```

Create a temporary appointment hold:

```bash
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
```

Book the hold:

```bash
curl -X POST http://127.0.0.1:8000/appointments/1/book
```

Create a diagnostic session and run a deterministic scripted turn:

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
```

Run the local Gather fallback webhook path without Twilio credentials:

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

Create an image upload link for a diagnostic session, inspect Mailpit, request a
presigned upload target, mark the upload complete, and run local deterministic
analysis:

```bash
curl -X POST http://127.0.0.1:8000/diagnostics/sessions/1/upload-link \
  -H "Content-Type: application/json" \
  -d '{"email":"caller@example.test"}'

curl -X POST http://127.0.0.1:8000/uploads/<token>/presigned-post \
  -H "Content-Type: application/json" \
  -d '{"filename":"fridge.png","content_type":"image/png","byte_size":512}'

curl -X POST http://127.0.0.1:8000/uploads/<token>/complete \
  -H "Content-Type: application/json" \
  -d '{"filename":"fridge.png","content_type":"image/png","byte_size":512}'

python -m app.workers.vision --upload-id <upload_id>
```

The upload token is the last path segment of the emailed upload URL. The
`presigned-post` response includes S3 form fields for browser upload. The React
frontend upload page consumes the token at `/uploads/<token>`.

## Testing

Backend implementation must include:

- Unit tests.
- Functional API tests.
- Integration tests against local Postgres.
- Alembic migration tests.
- Twilio signature validation tests.
- Scheduling race-condition tests.

Current backend checks:

```bash
cd backend
python -W error -m pytest
ruff check .
pip-audit
```

Tests cover the health endpoint, settings aliases, Alembic migrations from an
empty database, deterministic technician seed data, repository queries by ZIP
code plus appliance type, scheduling API flows, confirmation persistence,
double-booking rejection, cancellation slot release, concurrent hold races,
diagnostic state extraction, symptom memory, unsafe troubleshooting refusal,
tool-call validation, the OpenAI provider contract with a fake client, signed
Twilio webhook handling, Gather fallback turns, status callbacks, and the
ConversationRelay WebSocket handler. Phase 5 tests also cover upload token
expiry, image file validation, presigned POST generation, email rendering, queue
enqueueing, vision worker success/failure paths, and session history updates
after image analysis.

Phase 6 tests also cover strict CORS behavior for the configured frontend
origin and the local default upload-link URL used by the React app.

For local PostgreSQL verification, `alembic upgrade head` and `python -m app.seed`
were run against PostgreSQL 18. PostgreSQL 19 is not used because it is not GA.

Phase 2 PostgreSQL smoke verification additionally exercised:

- `GET /scheduling/matches`
- `POST /appointments/holds`
- duplicate hold returning HTTP `409 Conflict`
- `POST /appointments/{id}/book`
- `GET /appointments/{id}`

Phase 3 PostgreSQL smoke verification additionally exercised:

- `POST /diagnostics/sessions`
- `POST /diagnostics/sessions/{id}/turn`
- deterministic two-turn diagnostic state persistence
- `find_technician_matches` tool-call emission
- unsafe troubleshooting safety escalation

Phase 4 local smoke verification additionally exercises:

- `POST /twilio/voice/incoming`
- `POST /twilio/voice/gather`
- `POST /twilio/voice/status`
- `WebSocket /twilio/conversation`

Phase 5 local smoke verification additionally exercises:

- `POST /diagnostics/sessions/{id}/upload-link`
- `GET /uploads/{token}`
- `POST /uploads/{token}/presigned-post`
- `POST /uploads/{token}/complete`
- `python -m app.workers.vision --upload-id <upload_id>`

## Infrastructure

Backend AWS resources are managed from `backend/infra` using Terraform.
