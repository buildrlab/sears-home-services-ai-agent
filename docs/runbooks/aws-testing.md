# AWS Testing Runbook

All AWS infrastructure is deployed through Terraform and GitHub Actions. Do not create durable infrastructure manually in the AWS console.

## Prerequisites

- AWS region: `us-east-1`.
- Terraform state bootstrapped in S3.
- GitHub OIDC configured for deployments.
- GitHub environments configured with required secrets.
- BuildrLab core DNS access configured:
  - DNS account: `buildrlab-core`
  - DNS account ID: `202612164956`
  - Parent hosted zone: `buildrlab.com`
  - Cross-account DNS provider/role configured the same way as `website` and `buildr-hq`
- Route 53 records configured directly in the parent `buildrlab.com` hosted zone for:
  - `shs.buildrlab.com`
  - `api.shs.buildrlab.com`
  - `ws.shs.buildrlab.com`
- No child hosted zone exists for `shs.buildrlab.com` unless a later ADR changes the DNS model.
- Twilio phone number configured for the deployed voice webhook.
- Twilio ConversationRelay enabled, or Gather fallback explicitly selected.
- SES sender identity verified.
- OpenAI API key stored in AWS Secrets Manager or GitHub Actions secrets.

## Deployment Path

1. Open a pull request into `dev`.
2. Confirm backend, frontend, Terraform, and security checks pass.
3. Review the Terraform plan in GitHub Actions.
4. Confirm the DNS plan uses the cross-account `aws.dns` provider against the parent `buildrlab.com` hosted zone.
5. Confirm the DNS plan does not create a Sears-owned `shs.buildrlab.com` hosted zone.
6. Confirm the backend plan deploys ECS/Fargate services/tasks, not a Lambda API runtime.
7. Merge only after checks and plan are understood.
8. Deploy through the approved GitHub Actions workflow.

## Database Migrations

Production Alembic migrations must run outside the normal API runtime. Do not
run `alembic upgrade head` during container startup, FastAPI startup, Lambda
import, or request handling.

The Phase 7 deployment path must include an explicit migration step before
traffic is shifted to the new backend version. The preferred runner is a
one-off ECS/Fargate task in the application VPC, using the same backend image
as the API service and a least-privilege migration role:

```bash
alembic upgrade head
```

The migration task must read database credentials from AWS Secrets Manager and
must run with deployment-level concurrency controls so two migrations cannot run
at the same time.

## DNS Verification

Before API and frontend smoke tests:

```bash
dig +short shs.buildrlab.com
dig +short api.shs.buildrlab.com
dig +short ws.shs.buildrlab.com
```

See [DNS Delegation Runbook](dns-delegation.md).

## Remote Smoke Tests

After deployment, verify:

```bash
curl -f https://api.shs.buildrlab.com/health
```

Then run the project smoke suite once it exists:

```bash
cd backend
pytest tests/smoke --base-url https://api.shs.buildrlab.com
```

## Remote Frontend Tests

Run Playwright against the deployed frontend:

```bash
cd frontend
PLAYWRIGHT_BASE_URL=https://shs.buildrlab.com pnpm test:e2e
```

The run must pass without unexpected browser console errors.
Confirm the deployed frontend was built with
`VITE_API_BASE_URL=https://api.shs.buildrlab.com`.

## Twilio Verification

Call the configured Twilio number and verify:

- The call reaches `https://api.shs.buildrlab.com/twilio/voice/incoming`.
- ConversationRelay connects to `wss://ws.shs.buildrlab.com/twilio/conversation`, or Gather fallback works if ConversationRelay is unavailable.
- Twilio signatures are validated.
- A call session is persisted.
- Appliance and symptom collection works.
- Scheduling can book an appointment.

## Tier 3 Verification

During or after a call:

- Capture caller email.
- Send upload link through SES.
- Confirm the upload link points to `https://shs.buildrlab.com/uploads/<token>`.
- Confirm the email is received.
- Upload a valid appliance image.
- Confirm invalid file types and oversized files are rejected.
- Confirm image metadata is stored.
- Confirm OpenAI vision analysis runs.
- Confirm the diagnostic session shows the visual analysis result.

## AWS Log Review

After every remote test run, review:

- ALB target errors.
- ECS task crashes, deployment failures, and container health check failures.
- Aurora connection issues.
- SQS dead-letter queue messages.
- SES send failures.
- S3 access denied events.
- CloudWatch alarms.

Fix any observed runtime errors and rerun the relevant tests.

## Security Review

Before submission:

- Confirm no secrets are committed.
- Confirm Terraform uses least-privilege IAM.
- Confirm S3 buckets block public access unless explicitly justified.
- Confirm upload URLs are short-lived.
- Confirm CORS allows only expected origins.
- Confirm dependency and security scans pass.
- Confirm deployed resources are cost-conscious and unnecessary resources are removed.
