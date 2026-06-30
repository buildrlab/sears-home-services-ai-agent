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
```

The `SHS_`-prefixed aliases are also supported:

```text
SHS_DATABASE_URL=
SHS_ENVIRONMENT=
SHS_DATABASE_ECHO=
```

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

## Testing

Backend implementation must include:

- Unit tests.
- Functional API tests.
- Integration tests against local Postgres.
- Alembic migration tests.
- Twilio signature validation tests.
- Scheduling race-condition tests.

Current Phase 1 checks:

```bash
cd backend
python -W error -m pytest
ruff check .
pip-audit
```

Phase 1 tests cover the health endpoint, settings aliases, Alembic migration
from an empty database, deterministic technician seed data, and repository
queries by ZIP code plus appliance type.

For local PostgreSQL verification, `alembic upgrade head` and `python -m app.seed`
were run against PostgreSQL 18. PostgreSQL 19 is not used because it is not GA.

## Infrastructure

Backend AWS resources are managed from `backend/infra` using Terraform.
