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
TWILIO_PHONE_NUMBER=
TWILIO_TWIML_APP_SID=
```

`TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are required for API calls.
`TWILIO_PHONE_NUMBER` and `TWILIO_TWIML_APP_SID` are optional conveniences used by setup and verification commands.

Do not commit real values. Use a local uncommitted `.env` file, shell environment, GitHub Actions secrets, or AWS Secrets Manager.

## Script Catalog

| Script | Purpose | Mutates Twilio? | Status |
| --- | --- | --- | --- |
| `_client.py` | Shared standard-library Twilio REST helper for the scripts. | No | Implemented |
| `setup.py` | Validate credentials, find/create the SHS TwiML App, update webhook URLs, optionally associate a selected phone number, and print required environment values. | Yes | Implemented |
| `verify.py` | Inspect Twilio credentials, TwiML App, phone number, webhook URLs, and manual ConversationRelay readiness gates without making changes. | No | Implemented |
| `list_numbers.py` | Search available voice-capable local numbers and print candidates for manual selection. It does not purchase numbers. | No | Implemented |

When adding a script, update this table in the same commit.

## Verify Credentials

```bash
python3.14 scripts/twilio/verify.py --credentials-only
```

This validates the Twilio API credential without printing tokens.

## Search Available Numbers

```bash
python3.14 scripts/twilio/list_numbers.py --country US --area-code 212 --limit 10
```

Pick a number in Twilio, complete any required billing or regulatory setup, then export it as `TWILIO_PHONE_NUMBER`.

## Setup Command

```bash
python3.14 scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent" \
  --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status"
```

For local tunnel testing:

```bash
python3.14 scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent Local" \
  --voice-url "https://<tunnel-host>/twilio/voice/incoming" \
  --status-callback-url "https://<tunnel-host>/twilio/voice/status" \
  --dry-run
```

To attach a selected number:

```bash
export TWILIO_PHONE_NUMBER="+14155551234"

python3.14 scripts/twilio/setup.py \
  --friendly-name "SHS AI Agent" \
  --voice-url "https://api.shs.buildrlab.com/twilio/voice/incoming" \
  --status-callback-url "https://api.shs.buildrlab.com/twilio/voice/status" \
  --phone-number "$TWILIO_PHONE_NUMBER"
```

## Local Script Checks

```bash
PYTHONPYCACHEPREFIX=/private/tmp/shs-pycache python3.14 -m compileall scripts tests
PYTHONDONTWRITEBYTECODE=1 python3.14 -m unittest discover -s tests
ruff check scripts tests
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
