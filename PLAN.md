# Implementation Plan

## Objective

Build a fully working voice AI home appliance diagnostic agent for Sears Home Services. The system must handle inbound calls, guide appliance troubleshooting, schedule technicians, send secure image upload links, analyze uploaded appliance images, and deploy to AWS through Terraform while remaining runnable locally.

## Locked Decisions

- Organization: `buildrlab`
- Repository: `sears-home-services-ai-agent`
- Domain: `buildrlab.com`
- DNS account: `buildrlab-core` account `202612164956` owns the parent `buildrlab.com` hosted zone
- DNS pattern: match BuildrLab `website` and `buildr-hq`; use a cross-account Route 53 delegation role/provider to create Sears records directly in the parent hosted zone, with no Sears child hosted zone
- Frontend URL: `https://shs.buildrlab.com`
- API URL: `https://api.shs.buildrlab.com`
- Voice WebSocket URL: `wss://ws.shs.buildrlab.com/twilio/conversation`
- AWS region: `us-east-1`
- Integration branch: `dev`
- Release branch: `main`
- Backend: Python 3.14 in Amazon ECS/Fargate containers, FastAPI, SQLAlchemy 2.0, Alembic
- Frontend: React 19, Vite 8, TypeScript 6, Tailwind CSS 4
- Database: PostgreSQL 18 locally, latest Aurora Serverless v2 PostgreSQL-compatible minor on AWS
- Voice: Twilio ConversationRelay primary, Twilio Gather fallback
- Twilio provisioning: script-only using the Twilio API; do not use Terraform for Twilio
- AI: OpenAI Responses API, model configurable by environment
- Email: Amazon SES send-only, Mailpit locally
- Storage: S3 for uploaded appliance images, local S3-compatible storage for development
- Infrastructure: Terraform with S3 remote state
- CI/CD: GitHub Actions
- Dependency updates: grouped weekly Dependabot PRs targeting `dev`
- Database migrations: Alembic runs as an explicit deployment step outside normal API startup/request handling, through a one-off ECS/Fargate task in the application VPC.

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
| Phase 0.5: Twilio Access and Provisioning | Complete | Script-first Twilio automation, docs, CI, and local tests are implemented. Live Twilio credential verification passed, a selected phone number is available in the account, `setup.py` created the TwiML App and attached the number, `verify.py` confirmed webhook URLs plus phone routing, Gather fallback is the explicit Phase 0.5 live-call path, a real inbound call reached the smoke webhook, and the user reported Twilio was restored after the smoke test. | Keep ConversationRelay addendum/enablement as a Phase 4 gate. |
| Phase 1: Backend Foundation | Complete | FastAPI app factory, `/healthz`, settings, SQLAlchemy models, Alembic migration, seed data, repository queries, pytest coverage, Ruff, dependency audit, local run, and PostgreSQL 18 migration/seed verification are implemented. | Keep backend docs current as later phases expand the schema and API surface. |
| Phase 2: Scheduling Domain | Complete | Customer and appointment schema, transactional scheduling service, hold/book/cancel endpoints, active-slot uniqueness guard, confirmation persistence, API tests, concurrency tests, Ruff, local API run, and PostgreSQL 18 migration/API verification are implemented. | Keep scheduling service available as a deterministic tool for later voice/frontend flows. |
| Phase 3: Diagnostic Agent | Complete | Diagnostic session/event schema, deterministic agent workflow, appliance/symptom/ZIP extraction, safety refusal path, tool schemas, OpenAI Responses provider abstraction, API endpoints, tests, local API run, and PostgreSQL 18 migration/API verification are implemented. | Use diagnostic service from Phase 4 Twilio voice routes. |
| Phase 4: Twilio Voice | In Progress | Repo implementation is complete locally: signed webhook validation, Gather fallback, ConversationRelay TwiML/WebSocket handling, call-session persistence, Alembic migration, tests, and runbook updates are implemented. Live Twilio tunnel call-through and ConversationRelay account enablement remain the live-completion gates. | Run backend through ngrok/cloudflared with real Twilio auth token, verify a live Gather fallback call, and confirm ConversationRelay enablement or keep Gather as fallback. |
| Phase 5: Visual Diagnosis | Complete | Backend visual diagnosis is implemented and locally verified: email capture, upload-link email, hashed upload tokens, S3/MinIO presigned upload, upload metadata persistence, SQS-style worker entrypoint, deterministic/OpenAI vision providers, and session history updates. | Carry the upload APIs into the Phase 6 React upload UI. |
| Phase 6: Frontend | Complete | React/Vite/TypeScript/Tailwind frontend is implemented and locally verified with dashboard, upload page, unit/component tests, Playwright browser tests, strict CORS support, and dependency audits. | Carry the frontend build into Terraform/CloudFront in Phase 7. |
| Phase 7: Infrastructure | Next | Not started. | Implement Terraform for AWS resources, Fargate services/tasks, remote state, and an out-of-band Alembic migration runner. |
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
- Explicitly choose Gather fallback for Phase 0.5 if ConversationRelay access is not already confirmed.
- Defer Twilio Predictive and Generative AI/ML Features Addendum acceptance and ConversationRelay enablement confirmation to Phase 4 if Gather is used for Phase 0.5.
- Purchase or reserve a voice-capable phone number.
- Create a TwiML App for the SHS agent.
- Create least-privilege Twilio API credentials for automation.
- Store Twilio credentials only in GitHub Actions secrets or local uncommitted `.env` files.
- Add local setup instructions for ngrok/cloudflared tunneling.
- Add a local smoke webhook for inbound-call verification before the backend exists.
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

Implementation status:

- [x] Script-only Twilio ADR recorded.
- [x] `scripts/twilio/README.md` is the script catalog.
- [x] `scripts/twilio/_client.py` provides a small Twilio REST wrapper for setup scripts.
- [x] `scripts/twilio/setup.py` validates credentials, finds/creates/updates the TwiML App, supports `--dry-run`, normalizes formatted phone input to E.164, and can attach an existing Twilio phone number to the TwiML App.
- [x] `scripts/twilio/verify.py` validates credentials, expected webhook URLs, TwiML App state, and optional phone-number routing without mutating Twilio.
- [x] `scripts/twilio/list_numbers.py` lists available voice-capable local numbers without purchasing them.
- [x] `scripts/twilio/smoke_server.py` provides a local Gather-based inbound-call webhook for Phase 0.5 live-call verification.
- [x] Script unit tests cover request construction, redaction, validation, CLI help, and dry-run behavior.
- [x] Scripts CI compiles scripts, runs unit tests, and runs Ruff.
- [x] Twilio account access verified with real credentials.
- [x] Billing/trial status confirmed sufficient for live voice testing by a completed inbound call.
- [x] Voice-capable phone number assigned or purchased.
- [x] AI/ML addendum and ConversationRelay enablement are deferred to Phase 4, not Phase 0.5.
- [x] Gather fallback explicitly marked as the Phase 0.5 live-call path.
- [x] TwiML App created and phone-number association applied against real Twilio resources.
- [x] Independent `verify.py` check confirms the TwiML App webhook URLs and phone-number routing.
- [x] Real inbound call reaches the Phase 0.5 smoke webhook and records the expected events.

Latest live check:

- 2026-07-01: User reported Twilio was updated after the smoke test. Treat this as the restore confirmation for Phase 0.5; Codex could not independently verify the provider state because Twilio credentials are not loaded in the Codex shell.
- 2026-07-01: User placed a real inbound Twilio call through the ngrok tunnel to the Phase 0.5 smoke webhook. The smoke server recorded `voice_incoming`, returned HTTP 200 from `/twilio/voice/incoming`, recorded `gather_response` with speech result `Test.`, returned HTTP 200 from `/twilio/voice/gather`, recorded `status_callback` with `CallStatus=completed` and `CallDuration=22`, and returned HTTP 204 from `/twilio/voice/status`. This confirms the live phone number, TwiML App routing, Gather fallback, tunnel, and local smoke webhook path.
- 2026-06-30: Local smoke webhook was run on `127.0.0.1:8765`; `/healthz` returned OK, `POST /twilio/voice/incoming` returned Gather TwiML, `POST /twilio/voice/status` returned 204, and logged call fields were redacted. No external tunnel CLI was available in the Codex environment, so the real phone-call gate still requires ngrok or cloudflared.
- 2026-06-30: User ran `python3.14 scripts/twilio/verify.py --friendly-name "SHS AI Agent" --phone-number "[redacted E.164]" --expected-voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" --expected-status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status"`; credential validation passed, the TwiML App was found, Voice URL and status callback URL matched, phone routing was `True`, ConversationRelay remained unknown, Gather fallback remained available, and overall status was `True`.
- 2026-06-30: User ran `python3.14 scripts/twilio/setup.py --friendly-name "SHS AI Agent" --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status" --phone-number "[redacted E.164]"`; credential validation passed, the TwiML App action was `created`, and the selected phone resource action was `attached`.
- 2026-06-30: User ran `python3.14 scripts/twilio/setup.py --friendly-name "SHS AI Agent" --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status" --phone-number "[redacted E.164]" --dry-run`; credential validation passed, the TwiML App action was `would_create`, and the selected phone resource action was `would_attach_after_app_create`. This confirms the selected number exists in Twilio and setup planning works, but it does not yet create the TwiML App or attach the number.
- 2026-06-30: User ran `python3.14 scripts/twilio/list_numbers.py --country US --limit 5`; Twilio returned 5 available US voice-capable local numbers with `address=none`. No number has been purchased or assigned yet.
- 2026-06-30: User ran `python3.14 scripts/twilio/verify.py --credentials-only`; credential validation passed, TwiML App and phone-number checks were skipped, ConversationRelay remains unknown, and Gather fallback remains available.
- 2026-06-30: `python3.14 scripts/twilio/verify.py --credentials-only` failed because `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` were missing from the local environment. No Twilio account facts were verified.

Core checks:

- Twilio API credential can authenticate without exposing secrets.
- A Twilio number can reach a temporary local webhook through a secure tunnel.
- Gather fallback is marked as the guaranteed Phase 0.5 implementation path.
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

Implementation status:

- [x] FastAPI application structure and app factory.
- [x] `/healthz` endpoint verified through a local Uvicorn run.
- [x] Settings/configuration layer with `DATABASE_URL` and `SHS_DATABASE_URL` aliases.
- [x] SQLAlchemy models for technicians, service areas, specialties, and availability windows.
- [x] Alembic migration setup with an initial migration from an empty database.
- [x] Deterministic seed data for 6 technicians across ZIP codes, appliance specialties, and availability.
- [x] Repository layer with active technician listing and ZIP/appliance matching.
- [x] Pytest coverage for health, settings, migrations, seed idempotence, and repository queries.
- [x] Ruff linting passes.
- [x] Dependency audit passes with no known third-party vulnerabilities.
- [x] PostgreSQL 18 migration and seed verification completed against a temporary local container on port `55432`.

Latest verification:

- 2026-07-01: `python -W error -m pytest` passed with 9 tests and no warnings.
- 2026-07-01: `ruff check .` passed for backend.
- 2026-07-01: `pip-audit` reported no known vulnerabilities for third-party dependencies; the local editable backend package was skipped because it is not on PyPI.
- 2026-07-01: Local Uvicorn served `GET /healthz` with `{"status":"ok","service":"shs-ai-agent-backend","environment":"local"}`.
- 2026-07-01: Alembic upgraded a PostgreSQL 18 database from empty to `head`; seed inserted or verified 6 active technicians.
- 2026-07-01: PostgreSQL 19 was not adopted because official PostgreSQL 19 is beta-only, not GA; PostgreSQL 18 remains the newest stable supported major.

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

Implementation status:

- [x] Customer and appointment schema added with Alembic migration `0002_appointment_schema`.
- [x] Appointment active slot key is unique while a slot is held or booked, and cleared on cancellation to release capacity.
- [x] Scheduling service validates technician ZIP coverage, appliance specialty, and recurring availability windows.
- [x] Slot hold, book, cancel, get, list, and match operations are available through FastAPI endpoints.
- [x] Confirmation codes persist when held appointments are booked.
- [x] Double-booking protection is covered by deterministic API tests and repeated concurrent service tests.
- [x] Local PostgreSQL 18 migration and API smoke verification completed against a temporary container on port `55433`.

Latest verification:

- 2026-07-01: `python -W error -m pytest` passed with 22 tests and no warnings.
- 2026-07-01: `ruff check .` passed for backend.
- 2026-07-01: Alembic upgraded a PostgreSQL 18 database from empty through `0002_appointment_schema`.
- 2026-07-01: `python -m app.seed` inserted or verified 6 technicians in PostgreSQL 18.
- 2026-07-01: Local Uvicorn served `GET /healthz`, `GET /scheduling/matches`, `POST /appointments/holds`, `POST /appointments/{id}/book`, and `GET /appointments/{id}` against PostgreSQL 18.
- 2026-07-01: Duplicate hold for the same technician and scheduled start returned HTTP `409 Conflict` against PostgreSQL 18.

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

Implementation status:

- [x] Diagnostic session and diagnostic event schema added with Alembic migration `0003_diagnostic_schema`.
- [x] Deterministic local provider extracts appliance type, symptom memory, and ZIP code without an OpenAI key.
- [x] Safety guardrails refuse unsafe gas, smoke, fire, sparking, electrical shock, and carbon monoxide troubleshooting.
- [x] Tool schemas and validation added for technician matching, upload-link creation, and call-state updates.
- [x] OpenAI Responses API provider abstraction added with model/config values loaded from environment.
- [x] Diagnostic API supports session creation, session listing/fetching, and scripted turns.
- [x] Tests cover appliance extraction, symptom memory, avoiding repeated known-field questions, scheduling escalation, safety refusal, tool-call validation, and OpenAI provider contract calls.

Latest verification:

- 2026-07-01: `python -W error -m pytest` passed with 36 tests and no warnings after installing `openai==2.44.0`.
- 2026-07-01: `ruff check .` passed for backend.
- 2026-07-01: `pip-audit` reported no known vulnerabilities for third-party dependencies; the local editable backend package was skipped because it is not on PyPI.
- 2026-07-01: `compileall` passed for backend app/tests plus scripts.
- 2026-07-01: Twilio script unit tests still passed with 16 tests.
- 2026-07-01: Alembic upgraded a PostgreSQL 18 database from empty through `0003_diagnostic_schema`.
- 2026-07-01: Local Uvicorn served deterministic diagnostic session creation and two-turn scripted diagnostic flow against PostgreSQL 18.
- 2026-07-01: The deterministic flow persisted appliance `refrigerator`, symptoms `not cooling` and `leaking`, ZIP `75201`, status `ready_to_schedule`, and emitted `find_technician_matches`.
- 2026-07-01: The safety flow escalated a gas-smell prompt to `safety_escalated` without giving repair instructions.

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

Implementation status:

- [x] Inbound Twilio webhook added at `POST /twilio/voice/incoming`.
- [x] Gather fallback added at `POST /twilio/voice/gather`.
- [x] Status callback added at `POST /twilio/voice/status`.
- [x] ConversationRelay WebSocket handler added at `WebSocket /twilio/conversation`.
- [x] Twilio request signature validation implemented with the official Twilio SDK.
- [x] TwiML generation implemented with the official Twilio SDK.
- [x] Call sessions and call events persist through Alembic migration `0004_call_session_schema`.
- [x] Gather fallback drives the deterministic diagnostic service.
- [x] ConversationRelay setup/prompt events create call sessions and diagnostic turns.
- [x] Local tests cover signed webhook acceptance, missing signature rejection, signed WebSocket acceptance, unsigned WebSocket rejection, ConversationRelay TwiML, Gather diagnostic turns, status callbacks, and WebSocket prompt handling.
- [ ] Live backend call-through through ngrok/cloudflared with real Twilio request signatures.
- [ ] ConversationRelay account addendum/enablement confirmed in Twilio.
- [ ] Live ConversationRelay call-through verified, or Gather explicitly retained as the deployed fallback.

Latest verification:

- 2026-07-01: Installed `twilio==9.10.9` into the local backend virtual environment.
- 2026-07-01: `python -W error -m pytest` passed with 44 tests and no warnings.
- 2026-07-01: `ruff check .` passed for backend.
- 2026-07-01: `pip-audit` reported no known vulnerabilities for third-party dependencies; the local editable backend package was skipped because it is not on PyPI.
- 2026-07-01: `compileall` passed for backend app/tests plus scripts.
- 2026-07-01: Twilio script unit tests still passed with 16 tests.
- 2026-07-01: Alembic upgraded a PostgreSQL 18 database from empty through `0004_call_session_schema`.
- 2026-07-01: Local Uvicorn served `GET /healthz`, `GET /scheduling/matches`, `POST /twilio/voice/incoming`, `POST /twilio/voice/gather`, and `POST /twilio/voice/status` against PostgreSQL 18.
- 2026-07-01: Local Gather fallback smoke persisted call `CAPGLOCAL123` as `completed`, diagnostic status `ready_to_schedule`, appliance `refrigerator`, ZIP `75201`, and events `voice_incoming`, `gather_response`, `status_callback`.

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

Implementation status:

- [x] Diagnostic flow captures caller email from messages.
- [x] Deterministic diagnostic provider emits `create_upload_link` tool calls when the caller asks to upload an image and an email is available.
- [x] Image upload schema added with Alembic migration `0005_image_upload_schema`.
- [x] Upload tokens are generated with `secrets`, stored only as SHA-256 hashes, and expire.
- [x] Upload-link email rendering and delivery supports Mailpit locally and SES in AWS.
- [x] S3-compatible presigned POST creation supports MinIO locally and S3 in AWS.
- [x] Upload metadata persists content type, byte size, storage bucket/key, and lifecycle status.
- [x] Completion marks uploads `analysis_pending` and enqueues SQS-style vision jobs when configured.
- [x] Vision worker entrypoint can process an SQS message body or a local upload ID.
- [x] Vision analysis supports deterministic no-key local mode and OpenAI Responses image input when `OPENAI_API_KEY` is configured.
- [x] Analysis success and failure paths update upload status and diagnostic session history.
- [x] Backend API supports upload-link creation, token validation, presigned upload, completion, session upload listing, and local analysis trigger.

Latest verification:

- 2026-07-01: Verified latest stable `boto3` on PyPI as `1.43.38` and installed it into the local backend environment.
- 2026-07-01: `python -W error -m pytest` passed with 57 tests and no warnings.
- 2026-07-01: `ruff check .` passed for backend.
- 2026-07-01: `pip-audit` reported no known vulnerabilities for third-party dependencies; the local editable backend package was skipped because it is not on PyPI.
- 2026-07-01: `compileall` passed for backend app/tests plus scripts.
- 2026-07-01: Twilio script unit tests still passed with 16 tests.
- 2026-07-01: Alembic upgraded a PostgreSQL 18 database from empty through `0005_image_upload_schema`.
- 2026-07-01: Local Uvicorn served Phase 5 endpoints against PostgreSQL 18, Mailpit, and MinIO.
- 2026-07-01: Local smoke created a diagnostic session, captured refrigerator/leaking/ZIP state, sent an upload-link email to Mailpit, generated a MinIO presigned POST, uploaded a PNG through that form with HTTP 204 from MinIO, completed the upload, ran deterministic vision analysis, and confirmed an `analyze_image` event plus `analyzed` upload status in session history.

## Phase 6: Frontend

Deliverables:

- [x] React/Vite/TypeScript app.
- [x] Tailwind CSS v4 setup.
- [x] Secure upload page.
- [x] Upload success/status page.
- [x] Minimal reviewer dashboard for sessions, appointments, uploads, and diagnostic events.
- [x] Responsive, functional, good-looking UI.
- [x] Backend CORS allowlist for local and deployed frontend origins.
- [x] Frontend CI now runs lint, typecheck, unit tests, build, and Playwright.
- [x] Security CI now audits backend and frontend dependencies.

Core tests:

- [x] Upload page rendering.
- [x] Invalid token state.
- [x] File validation.
- [x] Successful upload flow.
- [x] Dashboard data rendering.
- [x] Playwright upload flow.

Exit criteria:

- [x] Frontend runs locally.
- [x] Playwright passes locally.
- [x] No browser console errors.

Latest local check:

- 2026-07-01: Verified frontend package versions before installation: React
  `19.2.7`, Vite `8.1.2`, TypeScript `6.0.3`, Tailwind CSS `4.3.2`,
  Vitest `4.1.9`, Playwright `1.61.1`, ESLint `10.6.0`, jsdom `29.1.1`,
  and lucide-react `1.22.0`.
- 2026-07-01: `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build`
  passed for the frontend using Node `26.4.0` and pnpm `11.9.0`.
- 2026-07-01: Local Vite server ran on `127.0.0.1:5174` because `5173` was
  occupied; `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174 pnpm test:e2e` passed
  with dashboard and upload page tests and no browser console errors.
- 2026-07-01: Backend CORS/default upload-link changes passed 58 pytest tests
  and Ruff.
- 2026-07-01: Backend `pip-audit` and frontend `pnpm audit --audit-level=moderate`
  both reported no known vulnerabilities.

## Phase 7: Infrastructure

Deliverables:

- Terraform bootstrap for S3 state bucket and locking strategy.
- Shared infrastructure for cross-account DNS, IAM/OIDC, VPC, and common security groups.
- BuildrLab-style Route 53 delegation role/provider wiring for `buildrlab-core` account `202612164956`.
- DNS records for `shs.buildrlab.com`, `api.shs.buildrlab.com`, and `ws.shs.buildrlab.com` created directly in the existing parent `buildrlab.com` hosted zone.
- Backend infrastructure for ALB, ECS/Fargate, ECR, Aurora Serverless v2, S3, SQS, SES, Secrets Manager, CloudWatch.
- Out-of-band Alembic migration runner as a one-off ECS/Fargate task inside the VPC.
- Frontend infrastructure for S3 static hosting and CloudFront.
- Environment variable and secret wiring.

Core tests:

- `terraform fmt -check`.
- `terraform validate`.
- Static Terraform security scan.
- GitHub Actions plan generation.
- Migration runner can apply Alembic without invoking the API service or running migrations in app startup.

Exit criteria:

- Terraform plans cleanly.
- DNS plan matches `website`/`buildr-hq`: no Sears child hosted zone, direct parent-zone records via `aws.dns`.
- AWS deployment path is documented.
- Alembic migration execution is documented as a deployment step outside API startup/request handling.

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
