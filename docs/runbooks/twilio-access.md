# Twilio Access Runbook

Run this early. Voice access should not be discovered as a blocker after backend implementation begins.

## Goal

Provision enough Twilio access to test a real inbound call locally and later against AWS.

## Required Twilio Setup

1. Confirm Twilio account access.
2. Confirm billing or trial status supports buying or using a voice-capable phone number.
3. Accept the Predictive and Generative AI/ML Features Addendum before the ConversationRelay implementation phase.
4. Confirm ConversationRelay is enabled before the ConversationRelay implementation phase.
5. Buy or assign a voice-capable phone number.
6. Create a TwiML App for the SHS diagnostic agent.
7. Create API credentials for the setup script.
8. Store credentials outside the repo.

## Planned Voice URLs

Production:

```text
https://api.shs.buildrlab.com/twilio/voice/incoming
wss://ws.shs.buildrlab.com/twilio/conversation
```

Local tunnel:

```text
https://<tunnel-host>/twilio/voice/incoming
wss://<tunnel-host>/twilio/conversation
```

## Required Secrets

Use local `.env` files for development and GitHub Actions secrets or AWS Secrets Manager for deployed environments.

```text
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_API_KEY_SID=
TWILIO_API_KEY_SECRET=
TWILIO_PHONE_NUMBER=
TWILIO_TWIML_APP_SID=
```

Do not commit real values.

## Provisioning Strategy

Use scripts for all Twilio setup. Do not manage Twilio resources in Terraform.

All Twilio scripts live in `scripts/twilio/`. That folder is the source of truth for script names, purpose, inputs, outputs, and examples.

Reasoning:

- Twilio account onboarding and AI/ML addendum acceptance are manual prerequisites.
- The local webhook URL changes during development when ngrok/cloudflared tunnels change.
- A script can update TwiML App webhook URLs quickly for local and AWS testing.
- Script output can print the exact SIDs and environment variables needed by the app.
- The setup can be idempotent and easier to debug.
- Twilio credentials and mutable Twilio state should not be stored in Terraform state.

Expected script-managed candidates:

- Validate Twilio credentials.
- Find or create the SHS TwiML App.
- Update the TwiML App Voice URL.
- Optionally search for available voice-capable numbers.
- Optionally attach the selected phone number to the TwiML App.
- Print `.env` values without writing secrets to the repo.

Expected manual prerequisites:

- Account creation.
- Billing/trial setup.
- Regulatory phone-number requirements.
- AI/ML addendum acceptance.
- ConversationRelay product enablement if gated by account settings.

Phase 0.5 live-call verification uses the standard Twilio Gather fallback path.
ConversationRelay remains the primary Phase 4 target, but it is not required to
prove that the phone number can reach local code.

## Script Commands

All commands run from the repo root.

Validate credentials only:

```bash
python3.14 scripts/twilio/verify.py --credentials-only
```

Search for available voice-capable local numbers:

```bash
python3.14 scripts/twilio/list_numbers.py --country US --area-code 212 --limit 10
```

Dry-run TwiML App setup:

```bash
python3.14 scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent" \
  --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status" \
  --dry-run
```

Apply TwiML App setup and optionally attach an existing number:

```bash
export TWILIO_PHONE_NUMBER="+14155551234"

python3.14 scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent" \
  --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status" \
  --phone-number "$TWILIO_PHONE_NUMBER"
```

The setup script accepts common phone-number formatting and normalizes it to
E.164 before calling Twilio. For example, `+1 (415) 555-1234` becomes
`+14155551234`.

If `--dry-run` finds no existing TwiML App and a phone number is provided, the
script should report:

```text
TwiML App action: would_create
Phone action: would_attach_after_app_create
```

That dry-run output means the script verified the phone number exists and can
plan the association, but the real setup command still needs to run once so the
new TwiML App SID exists.

Verify expected resources after setup:

```bash
python3.14 scripts/twilio/verify.py \
  --friendly-name "SHS AI Agent" \
  --phone-number "$TWILIO_PHONE_NUMBER" \
  --expected-voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --expected-status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status"
```

## Local Inbound Call Smoke Test

Use this smoke test before the backend exists. It proves that Twilio can reach a
local webhook through a secure tunnel and that standard Voice/Gather works.

Start the local smoke webhook:

```bash
python3.14 scripts/twilio/smoke_server.py --port 8765
```

Start a tunnel in a second terminal with either ngrok or cloudflared:

```bash
ngrok http 8765
```

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

Point the existing TwiML App to the tunnel URL:

```bash
export TWILIO_PHONE_NUMBER="+14155551234"
export TUNNEL_BASE_URL="https://<tunnel-host>"

python3.14 scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent" \
  --voice-url "$TUNNEL_BASE_URL/twilio/voice/incoming" \
  --status-callback-url "$TUNNEL_BASE_URL/twilio/voice/status" \
  --phone-number "$TWILIO_PHONE_NUMBER"
```

Verify Twilio is pointing at the tunnel:

```bash
python3.14 scripts/twilio/verify.py \
  --friendly-name "SHS AI Agent" \
  --phone-number "$TWILIO_PHONE_NUMBER" \
  --expected-voice-url "$TUNNEL_BASE_URL/twilio/voice/incoming" \
  --expected-status-callback-url "$TUNNEL_BASE_URL/twilio/voice/status"
```

Call the Twilio number. The smoke server should print and log:

- `voice_incoming`
- `gather_response` after you press a digit or say a short phrase
- `status_callback`

Restore the AWS URL after the smoke call:

```bash
python3.14 scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent" \
  --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status" \
  --phone-number "$TWILIO_PHONE_NUMBER"
```

Then verify the restore:

```bash
python3.14 scripts/twilio/verify.py \
  --friendly-name "SHS AI Agent" \
  --phone-number "$TWILIO_PHONE_NUMBER" \
  --expected-voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --expected-status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status"
```

## Setup Script Contract

The script should be safe to run repeatedly.

Required behavior:

- Read secrets from environment variables only.
- Never print auth tokens or API key secrets.
- Validate credentials before making changes.
- Support `--dry-run`.
- Support `--voice-url` and `--status-callback-url`.
- Support local tunnel URLs and deployed AWS URLs.
- Reuse an existing TwiML App by friendly name if present.
- Print a clear summary of created/updated resources.
- Exit non-zero on partial failure.

Planned command shape:

```bash
python3.14 scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent" \
  --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status"
```

Every script in `scripts/twilio/` must support:

```bash
python3.14 scripts/twilio/<script>.py --help
```

## Local Verification

For the Phase 0.5 smoke server:

1. Start `scripts/twilio/smoke_server.py`.
2. Start a secure tunnel with ngrok or cloudflared.
3. Point the TwiML App Voice URL to the tunnel URL.
4. Call the Twilio number.
5. Confirm the smoke server records `voice_incoming`, `gather_response`, and `status_callback`.
6. Restore the TwiML App Voice URL to the AWS URL.

After backend Twilio endpoints exist:

1. Start backend locally.
2. Start a secure tunnel with ngrok or cloudflared.
3. Point the TwiML App Voice URL to the tunnel URL.
4. Call the Twilio number.
5. Confirm the backend receives the signed webhook.
6. Confirm ConversationRelay connects over WebSocket, or Gather fallback responds.
7. Confirm a call session is created.

## Live-Complete Gate

Do not move Phase 0.5 to `Complete`, or move to Phase 1, until all of these are true:

- `python3.14 scripts/twilio/verify.py --credentials-only` passes with real Twilio credentials.
- Billing or trial status is confirmed sufficient for live voice testing.
- A voice-capable Twilio phone number is assigned or purchased.
- The TwiML App exists in Twilio and points to the current local tunnel or AWS webhook.
- The selected Twilio number routes to that TwiML App.
- ConversationRelay is enabled, or Gather fallback is explicitly chosen for the live path.
- A real inbound call reaches the webhook and produces the expected response.

Latest status as of 2026-07-01: Phase 0.5 live-call verification is complete. Twilio credential verification passed from the user's local environment, `list_numbers.py` returned available US voice-capable local numbers with no address requirement, `setup.py --dry-run` confirmed the selected redacted phone number exists and can be attached after TwiML App creation, the non-dry-run setup created the TwiML App and attached the selected number, `verify.py` confirmed AWS webhook URLs plus phone routing, and a real inbound call through ngrok reached the smoke webhook. The smoke server recorded `voice_incoming`, `gather_response` with speech result `Test.`, and `status_callback` with completed call status. The user reported Twilio was updated after the smoke test; Codex could not independently verify the restored provider state because Twilio credentials are not loaded in the Codex shell.

Operational follow-up: after any ngrok/cloudflared smoke test, restore the TwiML App to the AWS placeholder URL and run the restore verification command above. ConversationRelay addendum acceptance and enablement remain Phase 4 gates; Gather fallback is the completed Phase 0.5 live-call path.

## Completion Criteria

- Twilio account access is confirmed.
- Voice-capable number exists or can be provisioned.
- ConversationRelay addendum and enablement are deferred to Phase 4.
- Gather fallback path is confirmed with a real inbound call.
- Script-first automation path is implemented or explicitly blocked.
- Any remaining manual Twilio steps are documented.
