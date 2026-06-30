# ADR 0004: Use Scripted Twilio Provisioning Only

## Status

Accepted

## Context

The project needs a real Twilio phone number and webhook configuration early so voice testing does not block later implementation phases. The infrastructure strategy is Terraform-first for AWS, but Twilio has account-level prerequisites, frequently changing local webhook URLs, and product onboarding steps that are not suitable for Terraform.

Twilio setup has two different kinds of work:

- Manual/account prerequisites: account access, billing or trial limits, regulatory phone-number requirements, AI/ML addendum acceptance, and ConversationRelay enablement.
- Repeatable application configuration: TwiML App lookup/creation, webhook URL updates, phone-number association, and printing required environment variables.

The webhook URL also changes during local development because ngrok/cloudflared tunnel hostnames can change.

## Decision

Use small idempotent scripts around the Twilio API as the only automation path for Twilio application configuration.

Keep AWS infrastructure in Terraform. Do not manage Twilio resources with Terraform for this project.

All Twilio scripts live under `scripts/twilio/`, with `scripts/twilio/README.md` as the script catalog.

## Consequences

- Developers can quickly point Twilio at either local tunnel URLs or deployed AWS URLs.
- The setup path is easier to debug during the take-home.
- Manual prerequisites remain explicit instead of hidden behind failing automation.
- Script output can tell reviewers and operators exactly which SIDs and environment variables are needed.
- We must test the script carefully because it performs external side effects.
- Twilio secrets and mutable Twilio resource state stay out of Terraform state.

## Script Requirements

- Read secrets from environment variables only.
- Never print auth tokens or API key secrets.
- Support dry-run mode.
- Be idempotent: rerunning must not duplicate TwiML Apps or phone-number mappings.
- Print created/updated Twilio resource SIDs.
- Fail closed on partial or ambiguous state.
- Keep Twilio secrets out of Terraform state.
- Live under `scripts/twilio/`.
- Be listed in `scripts/twilio/README.md` with purpose, inputs, outputs, and examples.

## Alternatives Considered

- Terraform-managed Twilio setup: attractive for declarative infrastructure, but brittle for local tunnel changes, exposes Twilio state in Terraform state, and is incomplete for onboarding/addendum requirements.
- Fully manual setup: fast once, but hard to reproduce and weak for reviewer confidence.
- Direct console-only setup plus screenshots: insufficient for a high-quality engineering submission.

## Revisit Criteria

Do not revisit Terraform-managed Twilio resources during this take-home. Reconsider only in a future production hardening cycle if Twilio setup stabilizes, local tunnel updates are no longer needed, and storing Twilio resource state in Terraform is explicitly accepted.
