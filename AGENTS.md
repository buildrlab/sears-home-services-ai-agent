# Agent Instructions

This repository contains the Sears Home Services voice AI appliance diagnostic agent take-home project.

## Quality Bar

The reviewer will be checking code quality closely. Treat every change as production-grade work.

- Write clear, maintainable, typed code with small modules and explicit boundaries.
- Keep implementation choices pragmatic and justified by the product requirements.
- New backend code must have unit tests and functional/integration coverage.
- New frontend code must have unit/component coverage and Playwright coverage for user-facing flows.
- Phase completion requires local execution, tests, browser verification where relevant, and bug fixes before moving on.
- Do not move to a later phase while the current phase has unresolved live-completion gates, unless the user explicitly accepts that blocker and asks to proceed anyway.
- For external services, "repo-complete" is not complete: live credentials, real account access, deployed or tunneled callbacks, and provider-side settings must be verified before marking the phase complete.
- When tests, browser console logs, linting, security scans, or local runs expose defects, fix them and rerun the failing checks.
- Do not accept known flaky tests, ignored failures, or unexplained warnings as complete.
- Do not claim zero vulnerabilities; claim zero known vulnerabilities only after current scans pass.
- Keep local and AWS testing instructions current, simple, and copy-pasteable.
- If a command in `README.md` or `docs/runbooks/` stops working, update the docs in the same change that fixes the code.

## Version Currency Policy

Use the latest stable, generally available version of every technology unless a deployment platform or security constraint makes that impossible. Do not copy old defaults from templates.

- Before adding or upgrading a runtime, framework, GitHub Action, package, Docker image, Terraform provider, database engine, or CLI tool, verify the current latest stable version from the official source, package registry, or vendor documentation.
- Latest means stable GA, not beta, RC, nightly, canary, or preview, unless an ADR explicitly accepts that risk.
- If AWS Lambda, Aurora, GitHub Actions runners, browsers, or another platform does not support the absolute latest upstream version, use the newest version that platform supports and document the gap in `PLAN.md`, an ADR, or the relevant runbook.
- Do not use end-of-life, deprecated, or maintenance-only major versions.
- Prefer explicit current-version pins or current major action tags that Dependabot can update. Avoid unbounded stale pins and avoid `latest` Docker tags for durable app infrastructure.
- If the latest version breaks the build, treat that as a blocker to investigate. If we intentionally step back to an older version, record why and add a revisit condition.
- Dependabot must remain configured for weekly grouped updates against `dev`; do not leave dependency drift unreviewed.

Current verified baseline as of 2026-06-30:

- GitHub Actions: `actions/checkout@v7.0.0`, `actions/setup-python@v6.3.0`, `actions/setup-node@v6.4.0`, `pnpm/action-setup@v6.0.9`.
- Python: `python3.14` because it is the latest AWS Lambda-supported Python runtime.
- PostgreSQL: PostgreSQL 18, using the newest Aurora PostgreSQL-compatible minor on AWS and PostgreSQL 18 locally.
- Node.js: 26.4.0 for frontend builds.
- pnpm: 11.9.0.
- React: 19.2.7.
- Tailwind CSS: 4.3.2.
- Vite: 8.1.2.
- TypeScript: 6.0.3.
- FastAPI: 0.138.2.
- SQLAlchemy: 2.0.51.
- Alembic: 1.18.5.
- psycopg: 3.3.4.
- pydantic-settings: 2.14.2.
- Uvicorn: 0.49.0.
- pytest: 9.1.1.
- pytest-cov: 7.1.0.
- Ruff: 0.15.20.

Refresh this baseline before installing frontend/backend dependencies, before each deployment phase, and before final submission.

## Architecture Decisions

Large or durable architecture decisions must be recorded in `docs/adr/`.

Use ADRs for decisions such as:

- SQL vs NoSQL database selection.
- Twilio ConversationRelay vs Twilio Gather fallback.
- OpenAI model/API selection.
- AWS deployment topology.
- Terraform state and environment strategy.
- Security-sensitive tradeoffs.

ADRs should include context, decision, consequences, alternatives considered, and review date.

## Security, Cost, and Performance

- Follow secure defaults: least-privilege IAM, no committed secrets, strict CORS, request validation, and short-lived signed URLs.
- Validate Twilio webhook and WebSocket handshake signatures with the official Twilio SDK.
- Store production secrets in AWS Secrets Manager or GitHub Actions secrets, never in repository files.
- Use Terraform for all AWS infrastructure. Terraform remote state must be managed in S3.
- Match the existing BuildrLab `website` and `buildr-hq` DNS pattern: `buildrlab-core` account `202612164956` owns the `buildrlab.com` hosted zone, and Sears Terraform must use a cross-account Route 53 delegation role/provider to create records directly in that zone. Do not create a Sears child hosted zone unless a later ADR changes this.
- Keep AWS resources cost-conscious: serverless where appropriate, lifecycle rules for S3, small Lambda memory until measured, and no always-on services unless justified.
- Measure or document performance-critical paths, especially call latency, upload processing, and scheduling transactions.

## Testing Expectations

Every implementation phase must include:

- Backend unit tests with `pytest`.
- Backend functional/integration tests against local services.
- Alembic migration tests from an empty database.
- Frontend tests with Vitest/React Testing Library.
- Playwright tests for browser flows.
- Linting and formatting checks.
- Security and dependency scans.
- Local smoke verification with `docker compose`.

AWS-facing phases must also include:

- Deployment through GitHub Actions and Terraform, not manual console drift.
- Remote API smoke tests against `https://api.shs.buildrlab.com`.
- Playwright tests against `https://shs.buildrlab.com`.
- Twilio phone-call verification against the deployed webhook.
- SES upload-link verification.
- Image upload and vision-analysis verification.
- CloudWatch/log review for errors after the test run.

## Scripts

- Twilio automation must live under `scripts/twilio/`.
- Keep `scripts/twilio/README.md` current as the script catalog.
- Every Twilio script must support `--help`.
- Any Twilio script that mutates external state must support `--dry-run`.
- Scripts must read secrets from environment variables or explicit secret-manager integrations, never from committed files.
- Scripts must not print auth tokens, API key secrets, or private credentials.
- Prefer idempotent scripts that can be safely rerun.

## Prompt and Response Log

All human prompts and assistant responses related to this project must be appended to `PROMPTS.md`.

Rules:

- Append entries during each working session before final handoff.
- Preserve the prompt, the response, and any material implementation decisions.
- Summarize tool output rather than pasting huge logs.
- Redact secrets, tokens, API keys, account IDs when sensitive, phone numbers if not intended for reviewer disclosure, and private credentials.
- If a previous prompt was missed, add a backfill entry with the best available summary and mark it as backfilled.

## Branch and Review Policy

- `dev` is the integration branch.
- `main` is release-only.
- Dependabot updates target `dev`.
- Commit and push every coherent completed change set before moving to the next implementation slice.
- Do not merge dependency updates unless base branch, mergeability, and required checks are verified.
- Do not auto-commit unrelated local changes.
- All deploys to AWS must run through Terraform and GitHub Actions.
