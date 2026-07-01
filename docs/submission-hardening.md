# Submission Hardening

## Reviewer Entry Points

- Local reviewer smoke script: `scripts/reviewer/local_smoke.py`
- Final readiness audit: `scripts/reviewer/final_readiness.py`
- Local setup runbook: `docs/runbooks/local-testing.md`
- AWS deployment runbook: `docs/runbooks/aws-testing.md`
- Technical design: `docs/technical-design.md`
- ADRs: `docs/adr/`

## Local Review Flow

1. Start local dependencies.
2. Apply Alembic migrations.
3. Seed technician reference data.
4. Start the backend.
5. Optionally start the frontend.
6. Run `scripts/reviewer/local_smoke.py`.

The reviewer smoke script covers:

- Backend health.
- Diagnostic memory and scheduling intent.
- Technician match.
- Appointment hold and booking.
- Twilio Gather fallback.
- Upload link creation.
- S3/MinIO presigned object upload.
- Upload completion.
- Deterministic image analysis.
- Frontend shell and upload route when `--frontend-base-url` is supplied.

## Security Controls

- No secrets are committed.
- Production secrets are expected in GitHub Actions secrets or AWS Secrets
  Manager.
- Twilio webhooks and ConversationRelay WebSocket handshakes validate signatures
  when `TWILIO_AUTH_TOKEN` is configured.
- Upload tokens are random, hashed at rest, and time-limited.
- Upload presigned POSTs constrain content type and object size.
- CORS is allowlisted.
- S3 buckets use public access blocks and SSE-KMS in Terraform.
- CloudFront uses OAC for private frontend assets.
- Terraform provisions KMS keys, WAF managed rules, log retention, and
  least-privilege task roles.
- Alembic is not run during API startup or request handling.

## Cost Controls

- Aurora Serverless v2 is configured with low initial capacity.
- Fargate task CPU/memory are right-sized for the take-home workload.
- CloudFront uses `PriceClass_100` by default.
- S3 lifecycle rules expire old noncurrent object versions and incomplete
  multipart uploads.
- SQS DLQ keeps failed vision jobs inspectable without repeatedly retrying
  forever.
- NAT egress is explicit because private Fargate tasks need outbound access for
  OpenAI, SES/S3/SQS APIs, and Twilio callbacks.

## Performance Notes

- The API is stateless and horizontally scalable behind an ALB.
- The vision worker is separate from request handling.
- Image upload uses direct-to-S3 presigned POSTs so the API does not proxy large
  files.
- Database constraints enforce scheduling correctness under concurrency.
- Diagnostic and vision providers are abstracted so deterministic local mode and
  OpenAI-backed mode have the same service boundaries.

## Current Known Limitations

- AWS live deployment has not run from this Codex session because local AWS
  credentials are unavailable.
- GitHub deployment environment `prod`, environment-scoped variables, and
  environment-scoped secrets are not configured yet. Use
  `scripts/github/configure_deploy.py` after `gh auth login` to apply them.
- `dev` branch protection recommendations are documented but not applied.
  `scripts/github/configure_branch_protection.py` is available to apply the
  conservative policy after `gh auth login`.
- ConversationRelay account enablement remains a provider-side Twilio gate until
  confirmed in the Twilio account.
- Gather remains the reliable fallback path if ConversationRelay is unavailable.

## Pre-Submission Checklist

- [ ] `backend/.venv/bin/python -W error -m pytest` passes.
- [ ] `backend/.venv/bin/ruff check backend scripts tests` passes or equivalent
  scoped Ruff checks pass.
- [ ] `backend/.venv/bin/pip-audit` reports no known third-party vulnerabilities.
- [ ] Frontend lint/typecheck/unit/build/Playwright checks pass.
- [ ] `pnpm audit --audit-level=moderate` reports no known frontend
  vulnerabilities.
- [ ] `scripts/terraform/validate.sh` passes.
- [ ] Trivy secret scan passes.
- [ ] Trivy config scan passes or findings are explicitly justified.
- [ ] `scripts/reviewer/local_smoke.py` passes locally.
- [ ] `scripts/reviewer/final_readiness.py` passes after live deployment gates are
  satisfied.
- [ ] GitHub Actions checks are green on the final PR into `dev`.
- [ ] AWS deploy workflow runs in `plan` then `apply` mode.
- [ ] Remote smoke checks pass.
- [ ] Playwright passes against the deployed frontend.
- [ ] A real Twilio call reaches the deployed backend.
- [ ] SES sends and receives the upload-link email.
- [ ] Uploaded image analysis completes in AWS.
- [ ] CloudWatch, ALB, ECS, Aurora, SQS DLQ, SES, and browser console logs are
  reviewed after the remote test.
