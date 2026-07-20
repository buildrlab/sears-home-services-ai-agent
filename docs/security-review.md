# Security Review

Security checks for sears-home-services-ai-agent should stay lightweight enough to run during normal development.

## Baseline

- `bash scripts/repo-health.sh` reports tracked env files; use `STRICT_ENV_FILES=1` when those should fail the gate.
- Use existing secret scanners when present: none detected.
- Keep sample env files limited to placeholder values.
- Do not commit generated reports that contain credentials, tokens, or customer data.

## Review Prompts

- Does this change add a new external service, webhook, or token?
- Does this change expand access to production data or admin paths?
- Does this change introduce file upload, parsing, shell execution, or network callbacks?
- Does this change alter authentication, authorization, or billing behavior?

## Required Evidence

- Note the security-sensitive paths touched in the PR.
- Link to the test or manual check that covers the sensitive path.
- Document any skipped scanner and why it could not run locally.
