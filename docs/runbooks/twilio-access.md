# Twilio Access Runbook

Run this early. Voice access should not be discovered as a blocker after backend implementation begins.

## Goal

Provision enough Twilio access to test a real inbound call locally and later against AWS.

## Required Twilio Setup

1. Confirm Twilio account access.
2. Confirm billing or trial status supports buying or using a voice-capable phone number.
3. Accept the Predictive and Generative AI/ML Features Addendum for ConversationRelay.
4. Confirm ConversationRelay is enabled.
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
python scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent" \
  --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status"
```

Every script in `scripts/twilio/` must support:

```bash
python scripts/twilio/<script>.py --help
```

## Local Verification

After backend Twilio endpoints exist:

1. Start backend locally.
2. Start a secure tunnel with ngrok or cloudflared.
3. Point the TwiML App Voice URL to the tunnel URL.
4. Call the Twilio number.
5. Confirm the backend receives the signed webhook.
6. Confirm ConversationRelay connects over WebSocket, or Gather fallback responds.
7. Confirm a call session is created.

## Completion Criteria

- Twilio account access is confirmed.
- Voice-capable number exists or can be provisioned.
- ConversationRelay status is known.
- Gather fallback path is confirmed as available.
- Script-first automation path is implemented or explicitly blocked.
- Any remaining manual Twilio steps are documented.
