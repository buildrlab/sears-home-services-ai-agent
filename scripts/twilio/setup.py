#!/usr/bin/env python3
"""Create or update Twilio voice setup for the SHS AI agent."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _client import (  # noqa: E402
    MissingTwilioConfig,
    TwilioClient,
    TwilioConfig,
    TwilioScriptError,
    redact_account_sid,
    redact_sid,
    validate_application_sid,
    validate_e164,
    validate_https_url,
)

DEFAULT_FRIENDLY_NAME = "SHS AI Agent"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Idempotently create/update the SHS TwiML App and optionally "
            "attach an existing Twilio phone number to it."
        )
    )
    parser.add_argument(
        "--friendly-name",
        default=DEFAULT_FRIENDLY_NAME,
        help=f'TwiML App friendly name. Defaults to "{DEFAULT_FRIENDLY_NAME}".',
    )
    parser.add_argument(
        "--voice-url",
        required=True,
        help="HTTPS webhook URL Twilio calls for inbound voice requests.",
    )
    parser.add_argument(
        "--status-callback-url",
        help="Optional HTTPS status callback URL for Twilio call events.",
    )
    parser.add_argument(
        "--phone-number",
        default=os.environ.get("TWILIO_PHONE_NUMBER"),
        help="Optional existing E.164 Twilio number to attach to the TwiML App.",
    )
    parser.add_argument(
        "--application-sid",
        default=os.environ.get("TWILIO_TWIML_APP_SID"),
        help="Optional existing TwiML App SID to update instead of lookup by name.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print planned changes without mutating Twilio.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = run(args)
    except TwilioScriptError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_text_summary(result)
    return 0


def run(args: argparse.Namespace) -> dict[str, Any]:
    voice_url = validate_https_url(args.voice_url, label="--voice-url")
    status_callback_url = None
    if args.status_callback_url:
        status_callback_url = validate_https_url(
            args.status_callback_url, label="--status-callback-url"
        )

    phone_number = None
    if args.phone_number:
        phone_number = validate_e164(args.phone_number, label="--phone-number")

    application_sid = None
    if args.application_sid:
        application_sid = validate_application_sid(
            args.application_sid, label="--application-sid"
        )

    config = _load_config(args.dry_run)
    result: dict[str, Any] = {
        "account": {
            "configured": config is not None,
            "sid_suffix": redact_account_sid(config.account_sid if config else None),
        },
        "dry_run": args.dry_run,
        "friendly_name": args.friendly_name,
        "voice_url": voice_url,
        "status_callback_url": status_callback_url,
        "application": {
            "action": "not_checked",
            "sid": application_sid,
            "sid_redacted": redact_sid(application_sid),
        },
        "phone_number": {
            "requested": phone_number,
            "action": "not_requested" if not phone_number else "not_checked",
        },
        "manual_gates": [
            "Confirm Twilio billing/trial status supports live voice testing.",
            "Confirm AI/ML addendum acceptance before ConversationRelay testing.",
            "Confirm ConversationRelay is enabled; Gather remains the fallback.",
        ],
    }

    if config is None:
        result["credential_validation"] = "skipped_missing_env_dry_run"
        result["application"]["action"] = "would_create_or_update"
        if phone_number:
            result["phone_number"]["action"] = "would_attach_after_lookup"
        return result

    client = TwilioClient(config)
    client.validate_credentials()
    result["credential_validation"] = "passed"

    application = _resolve_application(
        client=client,
        application_sid=application_sid,
        friendly_name=args.friendly_name,
        dry_run=args.dry_run,
        voice_url=voice_url,
        status_callback_url=status_callback_url,
    )
    result["application"].update(application)

    if phone_number:
        phone_result = _resolve_phone_number(
            client=client,
            phone_number=phone_number,
            application_sid=application["sid"],
            dry_run=args.dry_run,
        )
        result["phone_number"].update(phone_result)

    return result


def _load_config(dry_run: bool) -> TwilioConfig | None:
    try:
        return TwilioConfig.from_env()
    except MissingTwilioConfig:
        if dry_run:
            return None
        raise


def _resolve_application(
    *,
    client: TwilioClient,
    application_sid: str | None,
    friendly_name: str,
    dry_run: bool,
    voice_url: str,
    status_callback_url: str | None,
) -> dict[str, Any]:
    if application_sid:
        application = client.get_application(application_sid)
        return _update_or_skip_application(
            client=client,
            application=application,
            friendly_name=friendly_name,
            dry_run=dry_run,
            voice_url=voice_url,
            status_callback_url=status_callback_url,
        )

    matches = client.list_applications(friendly_name=friendly_name)
    if len(matches) > 1:
        redacted = ", ".join(redact_sid(item.get("sid")) for item in matches)
        raise TwilioScriptError(
            f"Multiple TwiML Apps match friendly name {friendly_name!r}: {redacted}."
        )

    if matches:
        return _update_or_skip_application(
            client=client,
            application=matches[0],
            friendly_name=friendly_name,
            dry_run=dry_run,
            voice_url=voice_url,
            status_callback_url=status_callback_url,
        )

    if dry_run:
        return {
            "action": "would_create",
            "sid": None,
            "sid_redacted": "(not created)",
            "voice_url": voice_url,
            "status_callback_url": status_callback_url,
        }

    application = client.create_application(
        friendly_name=friendly_name,
        voice_url=voice_url,
        status_callback_url=status_callback_url,
    )
    return {
        "action": "created",
        "sid": application.get("sid"),
        "sid_redacted": redact_sid(application.get("sid")),
        "voice_url": application.get("voice_url") or voice_url,
        "status_callback_url": application.get("status_callback") or status_callback_url,
    }


def _update_or_skip_application(
    *,
    client: TwilioClient,
    application: dict[str, Any],
    friendly_name: str,
    dry_run: bool,
    voice_url: str,
    status_callback_url: str | None,
) -> dict[str, Any]:
    application_sid = application.get("sid")
    if not application_sid:
        raise TwilioScriptError("Twilio Application response did not include a SID.")

    changes = _application_changes(application, voice_url, status_callback_url)
    if not changes:
        return {
            "action": "unchanged",
            "sid": application_sid,
            "sid_redacted": redact_sid(application_sid),
            "voice_url": application.get("voice_url"),
            "status_callback_url": application.get("status_callback"),
        }

    if dry_run:
        return {
            "action": "would_update",
            "sid": application_sid,
            "sid_redacted": redact_sid(application_sid),
            "changes": changes,
            "voice_url": voice_url,
            "status_callback_url": status_callback_url,
        }

    updated = client.update_application(
        application_sid,
        friendly_name=friendly_name,
        voice_url=voice_url,
        status_callback_url=status_callback_url,
    )
    return {
        "action": "updated",
        "sid": updated.get("sid") or application_sid,
        "sid_redacted": redact_sid(updated.get("sid") or application_sid),
        "changes": changes,
        "voice_url": updated.get("voice_url") or voice_url,
        "status_callback_url": updated.get("status_callback") or status_callback_url,
    }


def _application_changes(
    application: dict[str, Any],
    voice_url: str,
    status_callback_url: str | None,
) -> dict[str, dict[str, Any]]:
    expected: dict[str, Any] = {
        "voice_url": voice_url,
        "voice_method": "POST",
    }
    if status_callback_url:
        expected["status_callback"] = status_callback_url
        expected["status_callback_method"] = "POST"

    return {
        key: {"from": application.get(key), "to": value}
        for key, value in expected.items()
        if application.get(key) != value
    }


def _resolve_phone_number(
    *,
    client: TwilioClient,
    phone_number: str,
    application_sid: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    if not application_sid:
        raise TwilioScriptError("Cannot attach a phone number without a TwiML App SID.")

    matches = client.list_incoming_phone_numbers(phone_number=phone_number)
    if not matches:
        raise TwilioScriptError(
            f"Phone number {phone_number} was not found in this Twilio account."
        )
    if len(matches) > 1:
        redacted = ", ".join(redact_sid(item.get("sid")) for item in matches)
        raise TwilioScriptError(f"Multiple phone resources matched {phone_number}: {redacted}.")

    phone = matches[0]
    phone_sid = phone.get("sid")
    if not phone_sid:
        raise TwilioScriptError("Twilio phone-number response did not include a SID.")

    current_application_sid = phone.get("voice_application_sid") or None
    if current_application_sid == application_sid:
        return {
            "requested": phone_number,
            "action": "unchanged",
            "sid": phone_sid,
            "sid_redacted": redact_sid(phone_sid),
            "voice_application_sid": application_sid,
        }

    if dry_run:
        return {
            "requested": phone_number,
            "action": "would_attach",
            "sid": phone_sid,
            "sid_redacted": redact_sid(phone_sid),
            "voice_application_sid": application_sid,
            "previous_voice_application_sid": current_application_sid,
        }

    updated = client.update_incoming_phone_number_application(
        phone_sid, application_sid=application_sid
    )
    return {
        "requested": phone_number,
        "action": "attached",
        "sid": updated.get("sid") or phone_sid,
        "sid_redacted": redact_sid(updated.get("sid") or phone_sid),
        "voice_application_sid": updated.get("voice_application_sid") or application_sid,
        "previous_voice_application_sid": current_application_sid,
    }


def print_text_summary(result: dict[str, Any]) -> None:
    print("Twilio setup summary")
    print(f"- Dry run: {result['dry_run']}")
    print(f"- Account SID suffix: {result['account']['sid_suffix']}")
    print(f"- Credential validation: {result.get('credential_validation', 'not_run')}")
    print(f"- Friendly name: {result['friendly_name']}")
    print(f"- Voice URL: {result['voice_url']}")
    print(f"- Status callback URL: {result.get('status_callback_url') or '(not set)'}")

    app = result["application"]
    print(f"- TwiML App action: {app['action']}")
    print(f"- TwiML App SID: {app.get('sid') or app.get('sid_redacted')}")

    phone = result["phone_number"]
    print(f"- Phone number: {phone.get('requested') or '(not requested)'}")
    print(f"- Phone action: {phone['action']}")
    if phone.get("sid"):
        print(f"- Phone resource SID: {phone['sid']}")

    print("- Manual gates:")
    for gate in result["manual_gates"]:
        print(f"  - {gate}")


if __name__ == "__main__":
    raise SystemExit(main())
