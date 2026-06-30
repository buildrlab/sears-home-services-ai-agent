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
ruff check .
pytest
```

Phase 1 and later must also include:

```bash
alembic upgrade head
pytest tests
```

## Script Checks

Twilio scripts do not call Twilio during local unit tests.

```bash
PYTHONPYCACHEPREFIX=/private/tmp/shs-pycache python3.14 -m compileall scripts tests
PYTHONDONTWRITEBYTECODE=1 python3.14 -m unittest discover -s tests
ruff check scripts tests
```

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
