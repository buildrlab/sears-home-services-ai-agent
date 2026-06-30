# Twilio Scripts

This folder is the source of truth for Twilio automation.

Twilio is script-managed for this project. Do not manage Twilio resources with Terraform.

## Rules

- Every script must support `--help`.
- Any script that mutates Twilio state must support `--dry-run`.
- Scripts must be idempotent where practical.
- Scripts must read secrets from environment variables or approved secret-manager integrations.
- Scripts must never print auth tokens, API key secrets, or private credentials.
- Scripts must print a clear summary of resources read, created, updated, or skipped.
- Scripts must exit non-zero on partial failure or ambiguous external state.
- Scripts must be safe to run against local tunnel URLs and deployed AWS URLs.

## Required Environment

```text
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_API_KEY_SID=
TWILIO_API_KEY_SECRET=
TWILIO_PHONE_NUMBER=
TWILIO_TWIML_APP_SID=
```

Do not commit real values. Use a local uncommitted `.env` file, shell environment, GitHub Actions secrets, or AWS Secrets Manager.

## Script Catalog

Planned scripts:

| Script | Purpose | Mutates Twilio? | Status |
| --- | --- | --- | --- |
| `setup.py` | Validate credentials, find/create the SHS TwiML App, update webhook URLs, optionally associate a selected phone number, and print required environment values. | Yes | Planned |
| `verify.py` | Inspect Twilio account, TwiML App, phone number, webhook URLs, and ConversationRelay readiness signals without making changes. | No | Planned |
| `list_numbers.py` | Search available voice-capable numbers and print candidates for manual selection. | No | Planned |

When adding a script, update this table in the same commit.

## Planned Setup Command

```bash
python scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent" \
  --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status"
```

For local tunnel testing:

```bash
python scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent Local" \
  --voice-url "https://<tunnel-host>/twilio/voice/incoming" \
  --status-callback-url "https://<tunnel-host>/twilio/voice/status" \
  --dry-run
```

## Output Contract

Scripts should print:

- Account SID suffix only, never the full credential set.
- TwiML App SID.
- Selected phone number in E.164 format only when safe to disclose.
- Voice URL.
- Status callback URL.
- Whether ConversationRelay is confirmed, unavailable, or unknown.
- Next manual action if setup cannot complete.

## Manual Prerequisites

These are not scriptable in this project:

- Twilio account creation.
- Billing/trial setup.
- Regulatory phone-number requirements.
- Predictive and Generative AI/ML Features Addendum acceptance.
- ConversationRelay product enablement if gated in the account.

