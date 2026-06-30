# AWS Testing Runbook

All AWS infrastructure is deployed through Terraform and GitHub Actions. Do not create durable infrastructure manually in the AWS console.

## Prerequisites

- AWS region: `us-east-1`.
- Terraform state bootstrapped in S3.
- GitHub OIDC configured for deployments.
- GitHub environments configured with required secrets.
- Route53 or DNS records configured for:
  - `shs.buildrlab.com`
  - `api.shs.buildrlab.com`
  - `ws.shs.buildrlab.com`
- Twilio phone number configured for the deployed voice webhook.
- Twilio ConversationRelay enabled, or Gather fallback explicitly selected.
- SES sender identity verified.
- OpenAI API key stored in AWS Secrets Manager or GitHub Actions secrets.

## Deployment Path

1. Open a pull request into `dev`.
2. Confirm backend, frontend, Terraform, and security checks pass.
3. Review the Terraform plan in GitHub Actions.
4. Merge only after checks and plan are understood.
5. Deploy through the approved GitHub Actions workflow.

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
- Confirm the email is received.
- Upload a valid appliance image.
- Confirm invalid file types and oversized files are rejected.
- Confirm image metadata is stored.
- Confirm OpenAI vision analysis runs.
- Confirm the diagnostic session shows the visual analysis result.

## AWS Log Review

After every remote test run, review:

- API Gateway errors.
- Lambda errors and timeouts.
- RDS Proxy or Aurora connection issues.
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
