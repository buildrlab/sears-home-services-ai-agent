# Technical Design

## Summary

The Sears Home Services AI Agent is a voice-first appliance diagnostic system.
It accepts inbound Twilio calls, drives a diagnostic conversation, schedules a
technician when needed, sends a secure appliance-photo upload link, analyzes the
uploaded image, and exposes a reviewer dashboard through a React frontend.

The implementation is intentionally deterministic locally. If `OPENAI_API_KEY`
is absent, text and vision providers use deterministic fallbacks so reviewers can
exercise Tier 1, Tier 2, and Tier 3 flows without paid API access.

## Requirement Mapping

| Requirement | Implementation |
| --- | --- |
| Tier 1 voice diagnostics | FastAPI Twilio routes, Gather fallback, ConversationRelay WebSocket route, diagnostic session/event model, deterministic and OpenAI providers. |
| Tier 2 scheduling | PostgreSQL-backed technician, service area, specialty, customer, and appointment schema with transactional hold/book/cancel logic. |
| Tier 3 visual diagnosis | Email upload-link flow, hashed upload tokens, S3/MinIO presigned upload, upload lifecycle persistence, worker-ready vision analysis service, deterministic/OpenAI vision providers. |
| Local run | Docker Compose for PostgreSQL 18, Mailpit, and MinIO; backend and frontend run locally with copy-pasteable runbooks. |
| AWS deploy | Terraform-managed shared, backend, and frontend stacks; backend on ECS/Fargate; frontend on S3/CloudFront; CI/CD through GitHub Actions. |

## Runtime Architecture

```text
Caller
  -> Twilio phone number
  -> FastAPI /twilio/voice/incoming
  -> ConversationRelay WebSocket or Gather fallback
  -> DiagnosticService
  -> PostgreSQL diagnostic/session state
  -> SchedulingService for technician matching and appointment booking
  -> SES/Mailpit upload link
  -> React upload page
  -> S3/MinIO image object
  -> SQS/local vision worker
  -> OpenAI or deterministic vision provider
```

## Backend

The backend is a Python 3.14 FastAPI application. It uses SQLAlchemy 2.0 and
Alembic for PostgreSQL schema management. The app is structured around route
modules, service modules, small provider abstractions, and Pydantic schemas.

Important boundaries:

- Routes translate HTTP/Twilio transport concerns into service calls.
- Services own transactional domain behavior.
- Provider abstractions isolate OpenAI, S3, SQS, SES, and Twilio SDK behavior.
- Alembic migrations are not run during startup.

## Database Choice

PostgreSQL is the primary datastore because scheduling requires relational
joins, transactional appointment holds, uniqueness constraints, and a simple
migration story. DynamoDB was considered and rejected for the primary scheduling
store because double-booking prevention and cross-entity reporting would require
more application-level coordination than this project needs. See
`docs/adr/0001-use-postgresql-for-scheduling.md`.

## Voice Flow

Twilio provisioning is script-managed under `scripts/twilio/`. Terraform does
not manage Twilio resources or secrets.

The backend supports:

- `POST /twilio/voice/incoming`
- `POST /twilio/voice/gather`
- `POST /twilio/voice/status`
- `WebSocket /twilio/conversation`

Gather is the guaranteed deployed reviewer path. ConversationRelay is
implemented and remains the preferred upgrade once the Twilio AI/ML addendum and
account feature gates are confirmed. Deployed validation posts production-signed
Twilio webhook requests and confirms the Gather flow, status callback, and call
session path.

## Scheduling Flow

Technician seed data records appliance specialties, ZIP service areas, and
weekly availability windows. Scheduling uses a transactional hold followed by a
booking call:

1. Find matches by ZIP and appliance type.
2. Validate technician service area, specialty, and availability.
3. Create a held appointment with an active slot uniqueness key.
4. Book the held appointment and generate a confirmation code.
5. Release expired holds and free cancelled slots.

This gives a clear correctness story for the reviewer: the database, not an
in-memory cache, prevents duplicate active bookings for the same technician and
slot.

## Visual Diagnosis Flow

Upload tokens are generated with `secrets`, stored only as SHA-256 hashes, and
expire. The upload flow is:

1. Caller email is captured or supplied.
2. Backend creates an upload token and sends the upload link.
3. Frontend validates the token.
4. Backend creates a content-type and size-limited presigned POST.
5. Browser uploads directly to S3/MinIO.
6. Backend marks upload completion and enqueues or locally runs analysis.
7. Vision provider records an analysis event on the diagnostic session.

The final AWS smoke verifies this flow end to end with SES, direct S3 upload,
OpenAI image analysis, and the diagnostic session history.

## Frontend

The frontend is React 19, Vite 8, TypeScript 6, and Tailwind CSS 4. It exposes:

- Reviewer dashboard for diagnostic sessions, appointments, uploads, and events.
- Upload route at `/uploads/<token>`.
- Client-side file validation.
- Playwright coverage for dashboard and upload flows.

## AWS Deployment

AWS infrastructure is Terraform-managed:

- `infra/shared`: VPC, subnets, NAT, ECS cluster.
- `backend/infra`: ECR, ALB, ECS/Fargate API and worker services, migration task,
  Aurora Serverless v2, S3 uploads, SQS/DLQ, SES, Secrets Manager, CloudWatch,
  ACM, and DNS records.
- `frontend/infra`: S3 static assets, CloudFront, WAF, ACM, and DNS records.

The Python layer runs on ECS/Fargate, not Lambda. Alembic runs through a one-off
Fargate migration task in the VPC as part of deployment.

## Verification Strategy

Local verification includes:

- Backend pytest, Ruff, and pip-audit.
- Alembic migration from an empty database.
- Frontend ESLint, TypeScript, Vitest, build, Playwright, and pnpm audit.
- Script compile/unit tests.
- Terraform fmt/init/validate.
- Trivy secret/config scans.
- Reviewer local smoke flow in `scripts/reviewer/local_smoke.py`.

Remote verification is documented in `docs/runbooks/aws-testing.md` and remains
blocked until GitHub deployment variables/secrets and AWS credentials are
available.
