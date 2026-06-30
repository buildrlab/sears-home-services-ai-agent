# Agent Instructions

This repository contains the Sears Home Services voice AI appliance diagnostic agent take-home project.

## Quality Bar

The reviewer will be checking code quality closely. Treat every change as production-grade work.

- Write clear, maintainable, typed code with small modules and explicit boundaries.
- Keep implementation choices pragmatic and justified by the product requirements.
- New backend code must have unit tests and functional/integration coverage.
- New frontend code must have unit/component coverage and Playwright coverage for user-facing flows.
- Phase completion requires local execution, tests, browser verification where relevant, and bug fixes before moving on.
- When tests, browser console logs, linting, security scans, or local runs expose defects, fix them and rerun the failing checks.
- Do not accept known flaky tests, ignored failures, or unexplained warnings as complete.
- Do not claim zero vulnerabilities; claim zero known vulnerabilities only after current scans pass.

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
- Do not merge dependency updates unless base branch, mergeability, and required checks are verified.
- Do not auto-commit unrelated local changes.
- All deploys to AWS must run through Terraform and GitHub Actions.

