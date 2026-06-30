# Implementation Plan

## Objective

Build a fully working voice AI home appliance diagnostic agent for Sears Home Services. The system must handle inbound calls, guide appliance troubleshooting, schedule technicians, send secure image upload links, analyze uploaded appliance images, and deploy to AWS through Terraform while remaining runnable locally.

## Locked Decisions

- Organization: `buildrlab`
- Repository: `sears-home-services-ai-agent`
- Domain: `buildrlab.com`
- Frontend URL: `https://shs.buildrlab.com`
- API URL: `https://api.shs.buildrlab.com`
- Voice WebSocket URL: `wss://ws.shs.buildrlab.com/twilio/conversation`
- AWS region: `us-east-1`
- Integration branch: `dev`
- Release branch: `main`
- Backend: Python, FastAPI, SQLAlchemy 2.0, Alembic
- Frontend: React, Vite, TypeScript, Tailwind CSS v4
- Database: PostgreSQL locally, Aurora Serverless v2 PostgreSQL on AWS
- Voice: Twilio ConversationRelay primary, Twilio Gather fallback
- AI: OpenAI Responses API, model configurable by environment
- Email: Amazon SES send-only, Mailpit locally
- Storage: S3 for uploaded appliance images, local S3-compatible storage for development
- Infrastructure: Terraform with S3 remote state
- CI/CD: GitHub Actions
- Dependency updates: grouped weekly Dependabot PRs targeting `dev`

## Repository Structure

```text
/
  backend/
    app/
    alembic/
    tests/
    infra/
    README.md
  frontend/
    src/
    tests/
    infra/
    README.md
  infra/
    bootstrap/
    shared/
  docs/
    adr/
  scripts/
  .github/
    workflows/
  AGENTS.md
  PLAN.md
  PROMPTS.md
  README.md
  docker-compose.yml
```

## Quality Gates

Every phase must finish with:

- Local app run.
- Unit tests.
- Functional/integration tests.
- Frontend/browser verification when UI is touched.
- Playwright tests for user-facing flows.
- Linting and formatting.
- Security/dependency scans.
- Bug fix pass after every console error, test failure, or runtime exception.
- `PROMPTS.md` updated with the prompt/response entry for the phase.

The target is zero known vulnerabilities at submission. This must be verified through current automated scans; it must not be asserted without evidence.

## Phase 0: Repository and Governance Foundation

Deliverables:

- Monorepo skeleton.
- Root `README.md`.
- `backend/README.md`.
- `frontend/README.md`.
- `PLAN.md`.
- `AGENTS.md`.
- `PROMPTS.md`.
- `.gitignore`, `.editorconfig`.
- GitHub Actions scaffolding for backend, frontend, Terraform, and security checks.
- Dependabot configuration for weekly grouped updates targeting `dev`.
- Initial ADRs for the durable architecture choices.

Exit criteria:

- Repo exists in GitHub.
- `main` and `dev` branches exist.
- CI files are present.
- Prompt logging policy is documented.

## Phase 1: Backend Foundation

Deliverables:

- FastAPI application structure.
- Health endpoint.
- Settings/configuration layer.
- SQLAlchemy models.
- Alembic migration setup.
- Local Postgres connection.
- Seed data for 5-10 technicians across ZIP codes, appliance specialties, and availability.
- Basic repository/service layer.
- Pytest setup.

Core tests:

- App health test.
- Settings validation tests.
- Migration from empty database.
- Technician seed data test.
- Repository query tests.

Exit criteria:

- Backend runs locally.
- Migrations apply from empty DB.
- Tests and Ruff checks pass.

## Phase 2: Scheduling Domain

Deliverables:

- Technician, service area, specialty, availability slot, customer, appointment schema.
- Scheduling service.
- Slot hold/book/cancel logic.
- Transactional booking with no double-booking.
- Admin/test API endpoints for sessions and appointments.

Core tests:

- Match by ZIP and appliance type.
- No technician match path.
- Booking success path.
- Concurrent double-booking prevention.
- Appointment confirmation persistence.

Exit criteria:

- Scheduling can be exercised through API tests.
- Race-condition tests pass repeatedly.

## Phase 3: Diagnostic Agent

Deliverables:

- Conversation state model.
- Appliance and symptom extraction.
- Diagnostic workflow.
- OpenAI provider abstraction.
- Tool schemas for scheduling, upload-link creation, and call state updates.
- Deterministic fallback for local tests without an OpenAI key.

Core tests:

- Appliance identification.
- Symptom memory.
- Does not re-ask known fields.
- Escalates to scheduling when unresolved.
- Refuses unsafe troubleshooting instructions.
- Tool-call validation.

Exit criteria:

- Agent can run deterministic scripted calls locally.
- OpenAI path is covered by contract tests/mocks.

## Phase 4: Twilio Voice

Deliverables:

- Inbound Twilio webhook.
- Twilio request signature validation.
- ConversationRelay TwiML generation.
- ConversationRelay WebSocket handler.
- Gather fallback mode.
- Call session event logging.
- Local ngrok/cloudflared instructions.

Core tests:

- Signed webhook accepted.
- Unsigned/invalid webhook rejected.
- TwiML generated correctly.
- WebSocket setup message creates session.
- Prompt messages update conversation state.
- Gather fallback can complete a scripted diagnostic turn.

Exit criteria:

- Local call can reach the app through a tunnel.
- ConversationRelay onboarding checklist is documented.
- Gather fallback works without ConversationRelay.

## Phase 5: Visual Diagnosis

Deliverables:

- Email capture in call flow.
- Upload token creation.
- SES send-only email integration.
- Mailpit local email testing.
- S3 presigned upload flow.
- Upload metadata persistence.
- SQS worker for vision analysis.
- OpenAI image analysis provider.
- Enhanced troubleshooting result attached to diagnostic session.

Core tests:

- Upload token expiry.
- File type and size validation.
- Presigned URL generation.
- Email rendering.
- Vision worker success/failure paths.
- Uploaded image result is visible in session history.

Exit criteria:

- Caller can receive upload link.
- User can upload image.
- Analysis updates diagnostic session.

## Phase 6: Frontend

Deliverables:

- React/Vite/TypeScript app.
- Tailwind CSS v4 setup.
- Secure upload page.
- Upload success/status page.
- Minimal reviewer dashboard for sessions, appointments, uploads, and diagnostic events.
- Responsive, functional, good-looking UI.

Core tests:

- Upload page rendering.
- Invalid token state.
- File validation.
- Successful upload flow.
- Dashboard data rendering.
- Playwright upload flow.

Exit criteria:

- Frontend runs locally.
- Playwright passes locally.
- No browser console errors.

## Phase 7: Infrastructure

Deliverables:

- Terraform bootstrap for S3 state bucket and locking strategy.
- Shared infrastructure for DNS, IAM/OIDC, VPC, and common security groups.
- Backend infrastructure for API Gateway, Lambda, Aurora Serverless v2, RDS Proxy, S3, SQS, SES, Secrets Manager, CloudWatch.
- Frontend infrastructure for S3 static hosting and CloudFront.
- Environment variable and secret wiring.

Core tests:

- `terraform fmt -check`.
- `terraform validate`.
- Static Terraform security scan.
- GitHub Actions plan generation.

Exit criteria:

- Terraform plans cleanly.
- AWS deployment path is documented.

## Phase 8: CI/CD and Remote Validation

Deliverables:

- GitHub Actions CI for backend.
- GitHub Actions CI for frontend.
- GitHub Actions Terraform plan/apply.
- GitHub Actions security scans.
- GitHub deployment environments.
- Branch protection recommendations.

Remote validation:

- Deploy dev environment.
- Run backend smoke tests against AWS API.
- Run Playwright against AWS frontend.
- Place real Twilio call to deployed webhook.
- Send SES upload email.
- Upload image and verify analysis.

Exit criteria:

- AWS environment passes smoke and Playwright tests.
- Live phone number is reviewer-ready.
- README contains final test number, availability window, and setup instructions.

## Phase 9: Submission Hardening

Deliverables:

- Technical design document.
- ADR completion.
- Final README polish.
- Known limitations.
- Cost notes.
- Security notes.
- Reviewer test script.
- Final vulnerability/dependency scan results.

Exit criteria:

- All local and AWS tests pass.
- Prompt log is updated.
- Reviewer can call the agent and complete the Tier 1, Tier 2, and Tier 3 flows.

## Prompt and Response Logging

All project prompts and assistant responses must be appended to `PROMPTS.md`.

For each entry include:

- Date/time.
- Author.
- Prompt or response.
- Decisions made.
- Files changed, if applicable.
- Verification performed.

Secrets must be redacted.

