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
- PostgreSQL.
- Local S3-compatible storage.
- Mailpit for email testing.

Detailed commands will be added as Phase 1 and Phase 6 are implemented.

## Deployment

All AWS infrastructure must be deployed with Terraform. Terraform state is managed in S3.

Planned subdomains:

- `shs.buildrlab.com`
- `api.shs.buildrlab.com`
- `ws.shs.buildrlab.com`

## Quality

This repo is built for code-review scrutiny. See `AGENTS.md` for engineering, security, testing, and prompt logging requirements.

