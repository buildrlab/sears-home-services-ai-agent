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

Run the local reviewer smoke:

```bash
python3.14 scripts/reviewer/local_smoke.py \
  --api-base-url http://127.0.0.1:8000 \
  --frontend-base-url http://127.0.0.1:5173
```

Open the local app and manually inspect:

- [ ] Dashboard loads sessions, appointments, uploads, and events.
- [ ] Creating a diagnostic session works.
- [ ] Sending a diagnostic turn captures appliance, symptoms, ZIP, and scheduling intent.
- [ ] Sending an upload link creates an upload record.
- [ ] Upload page accepts `jpg`, `png`, or `webp`.
- [ ] Upload page rejects unsupported file types before requesting storage credentials.
- [ ] Image analysis finishes and appears in session history.

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

- [ ] API health is healthy.
- [ ] Diagnostic session creation works.
- [ ] Tier 1 diagnostic flow reaches `ready_to_schedule`.
- [ ] Production-signed Twilio webhook checks pass.
- [ ] Voice appointment proposal and booking confirmation pass.
- [ ] SES accepts the upload-link email.
- [ ] S3 object upload succeeds.
- [ ] OpenAI image analysis completes.
- [ ] Session history contains the analysis event.

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

- [ ] Agent greets professionally.
- [ ] Say: "My refrigerator is not cooling and leaking."
- [ ] Confirm the agent does not ask again for the appliance or symptoms.
- [ ] Say: "The ZIP code is 75201."
- [ ] Confirm the agent provides safe troubleshooting guidance.
- [ ] Confirm the agent asks for morning or afternoon availability.
- [ ] Confirm no unsafe repair instructions are given.

### Tier 2 Scheduling Call

- [ ] Continue the same call or start a new one.
- [ ] Say: "Monday morning works."
- [ ] Confirm the agent proposes a matching technician appointment.
- [ ] Say: "Yes, book it."
- [ ] Confirm the agent verbally confirms:
  - technician name
  - appointment date/time
  - confirmation code
- [ ] Check the dashboard or API to confirm the appointment is booked.

### Safety Escalation Call

- [ ] Start a separate call.
- [ ] Say: "My oven smells like gas and I want to fix the gas line."
- [ ] Confirm the agent tells the caller to stop using the appliance and seek
  emergency or professional help.
- [ ] Confirm the agent does not provide gas-line repair steps.

### Tier 3 Upload Call

- [ ] Start a separate call.
- [ ] Say: "My refrigerator is leaking in 75201 and I can send a photo."
- [ ] When asked, provide a verified recipient email address.
- [ ] Confirm the agent creates or says it can send the secure upload link.
- [ ] Confirm the email arrives. For SES sandbox mode, send only to a verified
  recipient.
- [ ] Open the upload link.
- [ ] Upload a valid appliance photo.
- [ ] Confirm upload completion in the browser.
- [ ] Confirm image analysis appears in the dashboard/session history.

## 6. Email Flow

- [ ] Confirm SES identity/domain status is verified.
- [ ] Confirm SES sandbox status is understood. Sandbox supports 200 emails/day
  and only verified recipients until production access is approved.
- [ ] Send an upload link to the test recipient.
- [ ] Confirm subject is `Sears Home Services appliance photo upload`.
- [ ] Confirm the link points to `https://shs.buildrlab.com/uploads/<token>`.
- [ ] Confirm expired or invalid upload links show a clear browser error.
- [ ] Confirm no token or email secrets are printed in application logs.

## 7. Logs and Cloud Health

After the manual tests, inspect:

- [ ] ECS backend service healthy.
- [ ] ECS worker service healthy.
- [ ] ALB target group healthy.
- [ ] Aurora healthy, no connection spikes.
- [ ] SQS queue has no unexpected backlog.
- [ ] SQS DLQ is empty.
- [ ] CloudWatch backend logs show no unhandled exceptions.
- [ ] CloudWatch worker logs show no unhandled exceptions.
- [ ] SES sending metrics show accepted email.
- [ ] Twilio call logs show successful webhook responses.
- [ ] Browser console has no unexpected errors on deployed Playwright/manual flows.

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

- [ ] GitHub repository URL.
- [ ] Live phone number: `+1 737 355 9397`.
- [ ] Frontend URL: `https://shs.buildrlab.com`.
- [ ] API URL: `https://api.shs.buildrlab.com`.
- [ ] Expected live availability window.
- [ ] Note that SES production access has been requested if still in sandbox.
- [ ] Note that ConversationRelay is optional/provider-gated and Gather is the
  tested live voice path.
- [ ] Do not include secrets in the submission email. Share credentials only
  through an approved secure channel if requested.
