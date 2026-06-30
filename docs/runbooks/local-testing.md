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
pnpm test
pnpm build
pnpm test:e2e
```

Browser verification must include checking that the Playwright run and browser console show no unexpected errors.

## Full Local Smoke Test

When backend and frontend app code exists, the local smoke test must verify:

- Backend health endpoint responds.
- Migrations apply from an empty database.
- Technician seed data exists.
- Scheduling flow prevents double-booking.
- Frontend upload page renders.
- Upload token validation works.
- Mailpit receives the upload-link email.
- Image upload writes to local S3 storage.
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
