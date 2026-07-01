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
```

When no OpenAI API key is configured, the diagnostic agent uses the deterministic
local provider for repeatable local development and tests.

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
tool-call validation, and the OpenAI provider contract with a fake client.

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

## Infrastructure

Backend AWS resources are managed from `backend/infra` using Terraform.
