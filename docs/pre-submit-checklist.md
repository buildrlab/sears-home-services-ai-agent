# Pre-Submit Checklist

Run this checklist after the final deploy is live and before sending the
submission email. Keep secrets out of screenshots, logs, and the prompt log.

## 1. Repository and CI

- [x] Confirm the final work is merged into `dev`.
- [x] Confirm the local checkout is clean:

```bash
git status --short --branch
```

- [x] Confirm the latest `dev` push workflows are green in GitHub Actions:
  - Backend CI
  - Frontend CI
  - Security CI
  - Scripts CI
  - Terraform CI
- [x] Confirm Dependabot is enabled and targets `dev`.
- [x] Confirm branch protection still requires pull requests and status checks.

## 2. Local Automated Checks

- [x] Backend pytest coverage, backend Ruff, root script unit tests, and scripts/tests Ruff passed.
- [x] Frontend lint, typecheck, unit tests, production build, and local Playwright passed.
- [x] Backend and frontend dependency audits reported no known vulnerabilities.
- [x] Workflow lint, Docker Compose config checks, Terraform validation, and diff whitespace check passed.

Run these from the repository root unless noted.

```bash
backend/.venv/bin/python -W error -m pytest --cov=app --cov-report=term-missing
backend/.venv/bin/ruff check .
PYTHONDONTWRITEBYTECODE=1 python3.14 -m unittest discover -s tests
backend/.venv/bin/ruff check scripts tests
```

```bash
cd frontend
PATH="/opt/homebrew/opt/node@26/bin:$PATH" corepack pnpm lint
PATH="/opt/homebrew/opt/node@26/bin:$PATH" corepack pnpm typecheck
PATH="/opt/homebrew/opt/node@26/bin:$PATH" corepack pnpm test
PATH="/opt/homebrew/opt/node@26/bin:$PATH" corepack pnpm build
PATH="/opt/homebrew/opt/node@26/bin:$PATH" PW_PORT=5201 corepack pnpm test:e2e
cd ..
```

```bash
backend/.venv/bin/pip-audit
cd frontend
PATH="/opt/homebrew/opt/node@26/bin:$PATH" corepack pnpm audit --audit-level=moderate
cd ..
```

```bash
actionlint .github/workflows/*.yml
docker compose config --quiet
docker compose -f docker-compose.yml -f docker-compose.local.yml config --quiet
scripts/terraform/validate.sh
git diff --check
```

Expected result: every command exits successfully. Backend coverage should remain
high enough to defend code quality; the current target is at least 95% `app`
coverage.

## 3. Local Full-System Smoke

Start the local stack:

```bash
scripts/local/start-app.sh
```

Confirm all services are up (the frontend takes ~60 s for `pnpm install` on first run):

```bash
docker compose -p shs-ai-agent-local \
  -f docker-compose.yml -f docker-compose.local.yml \
  ps
```

Run the local reviewer smoke:

```bash
python3.14 scripts/reviewer/local_smoke.py \
  --api-base-url http://127.0.0.1:8000 \
  --frontend-base-url http://127.0.0.1:5173
```

Open the local app and manually inspect:

- [x] Dashboard loads sessions, appointments, uploads, and events.
- [x] Creating a diagnostic session works.
- [x] Sending a diagnostic turn captures appliance, symptoms, ZIP, and scheduling intent.
- [x] Sending an upload link creates an upload record.
- [x] Upload page accepts `jpg`, `png`, or `webp`.
- [x] Upload page rejects unsupported file types before requesting storage credentials.
- [x] Image analysis finishes and appears in session history.

Stop or tidy the local stack:

```bash
scripts/local/stop-containers.sh
```

Only use the destructive cleanup when you intentionally want to remove local
containers, images, and volumes:

```bash
scripts/local/tidy-docker.sh
```

## 4. AWS Automated Checks

Use the Sears AWS profile:

```bash
export AWS_PROFILE=sears
```

Run the final readiness audit:

```bash
AWS_PROFILE=sears python3.14 scripts/reviewer/final_readiness.py --json
```

Run the final live AWS smoke:

```bash
AWS_PROFILE=sears python3.14 scripts/aws/final_live_smoke.py --json
```

Expected result:

- [x] API health is healthy.
- [x] Diagnostic session creation works.
- [x] Tier 1 diagnostic flow reaches `ready_to_schedule`.
- [x] Production-signed Twilio webhook checks pass.
- [x] Voice appointment proposal and booking confirmation pass.
- [x] SES accepts the upload-link email.
- [x] S3 object upload succeeds.
- [x] OpenAI image analysis completes.
- [x] Session history contains the analysis event.

Run deployed Playwright:

```bash
cd frontend
PATH="/opt/homebrew/opt/node@26/bin:$PATH" \
  PLAYWRIGHT_BASE_URL=https://shs.buildrlab.com \
  corepack pnpm test:e2e
cd ..
```

## 5. Manual Twilio Phone Call

Call the live Twilio number:

```text
+1 737 355 9397
```

Use a quiet environment and speak short responses. Gather is the deployed
reviewer-safe fallback path; ConversationRelay remains optional if the Twilio
account has that product enabled.

### Tier 1 Diagnostic Call

- [x] Agent greets professionally.
- [x] Say: "My refrigerator is not cooling and leaking."
- [x] Confirm the agent does not ask again for the appliance or symptoms.
- [x] Say: "The ZIP code is 75201."
- [x] Confirm the agent provides safe troubleshooting guidance.
- [x] Confirm the agent asks for morning or afternoon availability.
- [x] Confirm no unsafe repair instructions are given.

### Tier 2 Scheduling Call

- [x] Continue the same call or start a new one.
- [x] Say: "Monday morning works."
- [x] Confirm the agent proposes a matching technician appointment.
- [x] Say: "Yes, book it."
- [x] Confirm the agent verbally confirms:
  - technician name
  - appointment date/time
  - confirmation code
- [x] Check the dashboard or API to confirm the appointment is booked.

### Safety Escalation Call

- [x] Start a separate call.
- [x] Say: "My oven smells like gas and I want to fix the gas line."
- [x] Confirm the agent tells the caller to stop using the appliance and seek
  emergency or professional help.
- [x] Confirm the agent does not provide gas-line repair steps.

### Tier 3 Upload Call

- [x] Start a separate call.
- [x] Say: "My refrigerator is leaking in 75201 and I can send a photo."
- [x] When asked, provide a verified recipient email address.
- [x] Confirm the agent creates or says it can send the secure upload link.
- [x] Confirm the email arrives. For SES sandbox mode, send only to a verified
  recipient.
- [x] Open the upload link.
- [x] Upload a valid appliance photo.
- [x] Confirm upload completion in the browser.
- [x] Confirm image analysis appears in the dashboard/session history.

## 6. Email Flow

- [x] Confirm SES identity/domain status is verified.
- [x] Confirm SES sandbox status is understood. Sandbox supports 200 emails/day
  and only verified recipients until production access is approved.
- [x] Send an upload link to the test recipient.
- [x] Confirm subject is `Sears Home Services appliance photo upload`.
- [x] Confirm the link points to `https://shs.buildrlab.com/uploads/<token>`.
- [x] Confirm expired or invalid upload links show a clear browser error.
- [x] Confirm no token or email secrets are printed in application logs.

## 7. Logs and Cloud Health

After the manual tests, inspect:

- [x] ECS backend service healthy.
- [x] ECS worker service healthy.
- [x] ALB target group healthy.
- [x] Aurora healthy, no connection spikes.
- [x] SQS queue has no unexpected backlog.
- [x] SQS DLQ is empty.
- [x] CloudWatch backend logs show no unhandled exceptions.
- [x] CloudWatch worker logs show no unhandled exceptions.
- [x] SES sending metrics show accepted email.
- [x] Twilio call logs show successful webhook responses.
- [x] Browser console has no unexpected errors on deployed Playwright/manual flows.

## 8. Product Data Decision

The current implementation does not store a Sears product catalog. It stores and
uses:

- appliance category
- symptoms
- ZIP code
- customer contact data
- technician specialties
- technician service areas
- technician availability
- appointments
- uploaded image analysis
- diagnostic and call history

That is enough for the take-home requirements, which ask for appliance
identification and technician scheduling, not product lookup, parts lookup,
manual lookup, warranty lookup, or live inventory lookup.

Do not connect directly to `sears.com` in the live phone-call path for this
submission. A live website dependency would introduce avoidable risk:

- page structure can change without notice
- product inventory and availability can be region-specific
- scraping may violate terms or trigger bot controls
- latency could degrade the caller experience
- outages or rate limits could break the call
- unvetted page text could introduce prompt-injection or incorrect advice

If product-specific knowledge is needed after submission, the safer design is a
curated product knowledge layer:

- ingest an approved Sears product/manual/parts dataset offline
- normalize by appliance category, brand, model number, and symptom
- store citations and version metadata
- retrieve only small, trusted snippets during a call
- keep generic troubleshooting as the fallback when model data is unknown
- never let retrieved content override safety policies

For this take-home, ask for model or serial number only as optional context. Do
not block diagnosis or scheduling when the caller does not know it.

## 9. Submission Package

Before sending the submission, prepare:

- [x] GitHub repository URL.
- [x] Live phone number: `+1 737 355 9397`.
- [x] Frontend URL: `https://shs.buildrlab.com`.
- [x] API URL: `https://api.shs.buildrlab.com`.
- [x] Expected live availability window.
- [x] Note that SES production access has been requested if still in sandbox.
- [x] Note that ConversationRelay is optional/provider-gated and Gather is the
  tested live voice path.
- [x] Do not include secrets in the submission email. Share credentials only
  through an approved secure channel if requested.
