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
- Twilio provisioning: script-only using the Twilio API; do not use Terraform for Twilio
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
    twilio/
  .github/
    workflows/
  AGENTS.md
  PLAN.md
  PROMPTS.md
  README.md
  docker-compose.yml
```

## Progress Tracker

Keep this table current after every phase or meaningful planning change.

| Phase | Status | Current outcome | Next action |
| --- | --- | --- | --- |
| Phase 0: Repository and Governance Foundation | Complete | Repo, docs, ADRs, CI scaffolding, Dependabot, prompt log, local/AWS runbooks are in place. | Keep docs current as implementation changes commands or workflows. |
| Phase 0.5: Twilio Access and Provisioning | Next | Not started. | Provision Twilio access early, confirm ConversationRelay onboarding path, and build script-first setup for supported Twilio resources. |
| Phase 1: Backend Foundation | Pending | Not started. | Build FastAPI, SQLAlchemy, Alembic, local Postgres, seed data, and tests. |
| Phase 2: Scheduling Domain | Pending | Not started. | Implement transactional scheduling and double-booking protection. |
| Phase 3: Diagnostic Agent | Pending | Not started. | Implement OpenAI-backed diagnostic workflow with deterministic test mode. |
| Phase 4: Twilio Voice | Pending | Not started. | Implement ConversationRelay and Gather fallback once access is confirmed. |
| Phase 5: Visual Diagnosis | Pending | Not started. | Implement upload email, S3 upload, SQS worker, and OpenAI vision analysis. |
| Phase 6: Frontend | Pending | Not started. | Build React/Tailwind upload and reviewer dashboard UI. |
| Phase 7: Infrastructure | Pending | Not started. | Implement Terraform for AWS resources and remote state. |
| Phase 8: CI/CD and Remote Validation | Pending | Not started. | Run GitHub Actions deploys and remote tests against AWS. |
| Phase 9: Submission Hardening | Pending | Not started. | Final docs, design doc, security scan, and reviewer test script. |

Status values: `Pending`, `Next`, `In Progress`, `Blocked`, `Complete`.

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
- README/runbook instructions updated for any command, environment variable, or workflow touched by the phase.

The target is zero known vulnerabilities at submission. This must be verified through current automated scans; it must not be asserted without evidence.

AWS-deployed phases must also finish with:

- Deployment through GitHub Actions and Terraform.
- Remote smoke tests against the deployed API.
- Playwright tests against the deployed frontend.
- Twilio live-call verification.
- SES email-link verification.
- Uploaded image analysis verification.
- CloudWatch/log review and bug fix pass.

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
- Local testing runbook.
- AWS testing runbook.

Exit criteria:

- Repo exists in GitHub.
- `main` and `dev` branches exist.
- CI files are present.
- Prompt logging policy is documented.
- Local and AWS testing instructions are documented and linked from the root README.

## Phase 0.5: Twilio Access and Provisioning

This phase must happen early so Twilio access does not block overnight implementation work.

Deliverables:

- Confirm Twilio account access.
- Confirm billing/trial status is sufficient for a live voice-capable phone number.
- Accept Twilio Predictive and Generative AI/ML Features Addendum if ConversationRelay is required.
- Confirm whether ConversationRelay is enabled on the account.
- Purchase or reserve a voice-capable phone number.
- Create a TwiML App for the SHS agent.
- Create least-privilege Twilio API credentials for automation.
- Store Twilio credentials only in GitHub Actions secrets or local uncommitted `.env` files.
- Add local setup instructions for ngrok/cloudflared tunneling.
- Implement idempotent Twilio setup scripts under `scripts/twilio/` for resources the API can safely manage.
- Use the setup script to create/update the TwiML App Voice URL and record required SIDs.
- Keep account onboarding, billing, regulatory requirements, AI/ML addendum acceptance, and ConversationRelay enablement as explicit manual prerequisites.
- Record the script-first provisioning decision in an ADR.

Automation note:

- AWS infrastructure must be Terraform-managed.
- Twilio infrastructure and application configuration must be script-managed through the Twilio API, not Terraform.
- `scripts/twilio/` is the source of truth for TwiML App setup, webhook URL updates, phone-number association, verification, and any future Twilio automation.
- Every Twilio script must be self-documenting with `--help`, dry-run support where it mutates external state, clear output, and a README entry.
- This avoids storing Twilio state/secrets in Terraform state and avoids provider coverage gaps.
- Twilio account onboarding, billing setup, phone-number regulatory requirements, and AI/ML addendum acceptance are expected to remain manual prerequisites.

Core checks:

- Twilio API credential can authenticate without exposing secrets.
- A Twilio number can reach a temporary local webhook through a secure tunnel.
- ConversationRelay availability is confirmed, or Gather fallback is marked as the guaranteed implementation path.
- Required Twilio values are documented as environment variables.
- Twilio setup script can run repeatedly without duplicating resources or leaking secrets.

Exit criteria:

- We know exactly which Twilio steps are automated and which are manual.
- A live Twilio number or confirmed provisioning path exists.
- The implementation can proceed overnight without waiting on account setup decisions.

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
