# Sears Home Services Voice AI Agent

Voice AI home appliance diagnostic agent for the Sears Home Services AI Engineer take-home project.

The system will support:

- Inbound phone calls through Twilio.
- Natural diagnostic conversation for appliance issues.
- Technician scheduling using PostgreSQL-backed availability.
- Secure image upload links sent by email.
- AI-assisted image analysis for enhanced troubleshooting.
- Local development with Docker Compose.
- AWS deployment through Terraform and GitHub Actions.

## Architecture

```text
Caller
  -> Twilio phone number
  -> FastAPI voice webhook
  -> Twilio ConversationRelay WebSocket or Gather fallback
  -> Diagnostic agent using OpenAI
  -> PostgreSQL scheduling data
  -> SES email link
  -> React upload page
  -> S3 image storage
  -> SQS vision worker
```

## Repository Layout

```text
backend/   Python FastAPI API, Alembic migrations, backend Terraform
frontend/  React/Vite/TypeScript/Tailwind v4 app and frontend Terraform
infra/     Bootstrap and shared AWS Terraform
docs/adr/  Architecture decision records
```

## Local Development

The local stack will run with Docker Compose and include:

- Backend API.
- Frontend app.
- PostgreSQL 18.
- Local S3-compatible storage.
- Mailpit for email testing.

Start local dependencies:

```bash
docker compose up -d postgres mailpit minio
```

Run backend checks:

```bash
cd backend
python3.14 -m pip install -e ".[dev]"
python -W error -m pytest
ruff check .
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Smoke test the backend:

```bash
curl http://127.0.0.1:8000/healthz
curl "http://127.0.0.1:8000/scheduling/matches?zip_code=75201&appliance_type=refrigerator"
curl -X POST http://127.0.0.1:8000/diagnostics/sessions \
  -H "Content-Type: application/json" \
  -d '{"customer_phone":"+15551234567"}'
```

After creating a diagnostic session, generate a secure appliance photo upload
link:

```bash
curl -X POST http://127.0.0.1:8000/diagnostics/sessions/1/upload-link \
  -H "Content-Type: application/json" \
  -d '{"email":"caller@example.test"}'
```

Mailpit shows the upload-link email at `http://127.0.0.1:8025`. See the local
testing runbook for the presigned upload and vision-analysis smoke flow.

Run frontend checks after frontend dependencies are installed:

```bash
cd frontend
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

Run the frontend locally:

```bash
cd frontend
pnpm dev
```

The upload page is served at `http://127.0.0.1:5173/uploads/<token>`.

Stop local dependencies:

```bash
docker compose down
```

See [Local Testing Runbook](docs/runbooks/local-testing.md) for the full phase-by-phase local validation ladder.

## Deployment

All AWS infrastructure must be deployed with Terraform. Terraform state is managed in S3.

Planned subdomains:

- `shs.buildrlab.com`
- `api.shs.buildrlab.com`
- `ws.shs.buildrlab.com`

DNS follows the existing BuildrLab `website` and `buildr-hq` pattern. The parent `buildrlab.com` hosted zone lives in `buildrlab-core` account `202612164956`; Sears Terraform will use a cross-account Route 53 delegation role/provider to create records directly in that hosted zone. It should not create a separate `shs.buildrlab.com` child hosted zone.

AWS validation must run after deployment and include API smoke tests, frontend Playwright tests against `https://shs.buildrlab.com`, Twilio call testing, SES upload-link testing, and image-analysis verification.

See [AWS Testing Runbook](docs/runbooks/aws-testing.md) for deployment and remote validation instructions.
See [DNS Delegation Runbook](docs/runbooks/dns-delegation.md) for the BuildrLab cross-account DNS pattern.

## Twilio Access

Twilio should be provisioned early. ConversationRelay requires account onboarding and AI/ML addendum acceptance before it can be the primary voice path. If ConversationRelay is not enabled in time, Twilio Gather remains the guaranteed fallback path.

All Twilio automation lives under `scripts/twilio/` and is script-managed, not Terraform-managed.

Initial script checks:

```bash
python3.14 scripts/twilio/verify.py --credentials-only
python3.14 scripts/twilio/setup.py --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" --dry-run
```

Phase 0.5 local call smoke test:

```bash
python3.14 scripts/twilio/smoke_server.py --port 8765
```

Expose that server with ngrok or cloudflared, point the TwiML App at the tunnel
with `scripts/twilio/setup.py`, call the Twilio number, then restore the AWS URL.
The smoke server returns Gather TwiML and records redacted inbound-call events.

See [Twilio Access Runbook](docs/runbooks/twilio-access.md).

## Quality

This repo is built for code-review scrutiny. Security, maintainability, performance, cost control, and test coverage are release gates, not nice-to-have items.

See `AGENTS.md` for engineering, security, testing, and prompt logging requirements.
