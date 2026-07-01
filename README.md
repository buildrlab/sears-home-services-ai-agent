# Sears Home Services Voice AI Agent

Voice AI home appliance diagnostic agent for the Sears Home Services AI Engineer take-home project.

The system supports:

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
backend/        Python FastAPI API, Alembic migrations, backend Terraform
frontend/       React/Vite/TypeScript/Tailwind v4 app and frontend Terraform
infra/          Bootstrap and shared AWS Terraform
docs/adr/       Architecture decision records
scripts/local/  Local Docker Compose and CI-matching utility scripts
scripts/        Twilio automation, Terraform helpers, and AWS verification scripts
```

## Local Development

The local stack runs with Docker Compose and includes:

- Backend API.
- Frontend app.
- PostgreSQL 18.
- Local S3-compatible storage.
- Mailpit for email testing.

Start the full local app with Docker Compose:

```bash
scripts/local/start-app.sh
```

This starts PostgreSQL, Mailpit, MinIO, applies Alembic migrations, seeds
technician data, creates the local MinIO upload bucket, runs the backend at
`http://127.0.0.1:8000`, and runs the frontend at `http://127.0.0.1:5173`.

Stop the local app:

```bash
scripts/local/stop-containers.sh
```

Remove local SHS Compose containers, project volumes, and local Compose images:

```bash
scripts/local/tidy-docker.sh --force
```

Run the local reviewer smoke flow after the app is up:

```bash
scripts/local/smoke-local.sh
```

Start only local dependencies for manual backend/frontend runs:

```bash
docker compose up -d postgres mailpit minio
```

Run backend checks:

```bash
cd backend
cp .env.example .env
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
scripts/local/lint-frontend.sh
scripts/local/test-frontend.sh
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
See [Local Utility Scripts](scripts/local/README.md) for Docker lifecycle,
cleanup, and CI-matching lint/test commands.

## Deployment

All AWS infrastructure must be deployed with Terraform. Terraform state is
managed in S3 with native S3 lockfiles.

Planned subdomains:

- `shs.buildrlab.com`
- `api.shs.buildrlab.com`
- `ws.shs.buildrlab.com`

DNS follows the existing BuildrLab `website` and `buildr-hq` pattern. The parent `buildrlab.com` hosted zone lives in `buildrlab-core` account `202612164956`; Sears Terraform will use a cross-account Route 53 delegation role/provider to create records directly in that hosted zone. It should not create a separate `shs.buildrlab.com` child hosted zone.

The Sears workload account for the production take-home environment is
`710045722740`.

Validate all Terraform stacks locally without deploying:

```bash
scripts/terraform/validate.sh
```

Deployment order:

1. `infra/bootstrap`
2. `infra/shared`
3. `backend/infra`
4. `frontend/infra`

The Python backend runs on ECS/Fargate. Alembic migrations run through an
explicit one-off Fargate task definition from `backend/infra`, not during API
startup.

GitHub Actions deployment workflow:

```text
.github/workflows/aws-deploy.yml
```

The workflow assumes the S3 Terraform state bucket already exists, then plans or
applies `infra/shared`, `backend/infra`, and `frontend/infra`. First backend
deploys must run with `bootstrap_backend=true` so ECR, Secrets Manager, Aurora,
and task definitions exist before the first image is pushed. The workflow then
pushes the backend image, verifies required runtime secrets, applies ECS service
desired counts, runs the Alembic Fargate task, builds/uploads the frontend, and
executes `scripts/aws/remote_smoke.py`.

AWS validation must run after deployment and include API smoke tests, frontend Playwright tests against `https://shs.buildrlab.com`, Twilio live-path testing, SES upload-link testing, and image-analysis verification.

Final live AWS smoke:

```bash
AWS_PROFILE=sears python3.14 scripts/aws/final_live_smoke.py \
  --api-base-url https://api.shs.buildrlab.com \
  --email-to no-reply@shs.buildrlab.com
```

The configured Twilio test number is `+17373559397`. The deployed reviewer
voice path uses Twilio Gather unless ConversationRelay is enabled in the Twilio
account. The voice flow provides safe troubleshooting, collects availability,
proposes a technician slot, books after caller confirmation, and reads back the
confirmation code. SES send is implemented and verified; the AWS account is in
sandbox mode with a 200 emails/day quota and production access requested.

See [AWS Testing Runbook](docs/runbooks/aws-testing.md) for deployment and remote validation instructions.
See [DNS Delegation Runbook](docs/runbooks/dns-delegation.md) for the BuildrLab cross-account DNS pattern.
See [GitHub Branch Protection Runbook](docs/runbooks/github-branch-protection.md) for recommended merge gates.
See [Technical Design](docs/technical-design.md) and [Submission Hardening](docs/submission-hardening.md) for reviewer-facing architecture, security, cost, and known-limitations notes.
See [GitHub Scripts](scripts/github/README.md) for deployment environment setup automation.

Manual AWS teardown is available through `.github/workflows/aws-destroy.yml`.
Run it in `plan` mode first. To remove resources after the project is over, run
it with `mode=destroy`, `delete_data=true`, and confirmation text
`destroy sears-home-services-ai-agent prod`. The workflow destroys frontend,
backend, and optionally shared workload resources, but intentionally retains the
shared Terraform state bucket.

## Reviewer Smoke Test

After starting the local backend and dependencies, run the reviewer smoke flow:

```bash
python3.14 scripts/reviewer/local_smoke.py \
  --api-base-url http://127.0.0.1:8000
```

Add `--frontend-base-url http://127.0.0.1:5173` when the Vite frontend is also
running. See [Reviewer Scripts](scripts/reviewer/README.md).

Before final submission, run the read-only readiness audit:

```bash
python3.14 scripts/reviewer/final_readiness.py
```

This audit fails closed until the live GitHub/AWS deployment gates pass. A
nonzero result is expected before `gh` auth, AWS credentials, GitHub deployment
configuration, branch protection, and remote smoke tests are complete.

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
