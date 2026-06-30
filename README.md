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
ruff check .
pytest
```

Run frontend checks after frontend dependencies are installed:

```bash
cd frontend
pnpm install
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
```

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

See [Twilio Access Runbook](docs/runbooks/twilio-access.md).

## Quality

This repo is built for code-review scrutiny. Security, maintainability, performance, cost control, and test coverage are release gates, not nice-to-have items.

See `AGENTS.md` for engineering, security, testing, and prompt logging requirements.
