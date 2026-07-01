#!/usr/bin/env python3
"""Verify Twilio access and expected voice resources without changing Twilio."""

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
        description="Verify Twilio credentials, TwiML App, and optional phone setup."
    )
    parser.add_argument(
        "--friendly-name",
        default=DEFAULT_FRIENDLY_NAME,
        help="TwiML App friendly name to find when --application-sid is absent.",
    )
    parser.add_argument(
        "--application-sid",
        default=os.environ.get("TWILIO_TWIML_APP_SID"),
        help="Existing TwiML App SID to verify.",
    )
    parser.add_argument(
        "--phone-number",
        default=os.environ.get("TWILIO_PHONE_NUMBER"),
        help="Optional E.164 Twilio number expected to route to the TwiML App.",
    )
    parser.add_argument(
        "--expected-voice-url",
        help="Optional expected TwiML App Voice URL. Fails verification on mismatch.",
    )
    parser.add_argument(
        "--expected-status-callback-url",
        help="Optional expected TwiML App status callback URL. Fails verification on mismatch.",
    )
    parser.add_argument(
        "--credentials-only",
        action="store_true",
        help="Only verify TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN.",
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
    return 0 if result["ok"] else 1


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = TwilioConfig.from_env()
    client = TwilioClient(config)
    client.validate_credentials()

    result: dict[str, Any] = {
        "ok": True,
        "account": {"sid_suffix": redact_account_sid(config.account_sid)},
        "credential_validation": "passed",
        "application": {"checked": False},
        "phone_number": {"checked": False},
        "manual_gates": {
            "conversationrelay": "unknown_manual_account_check_required",
            "gather_fallback": "available_in_standard_twilio_voice",
        },
    }

    if args.credentials_only:
        return result

    expected_voice_url = None
    if args.expected_voice_url:
        expected_voice_url = validate_https_url(
            args.expected_voice_url, label="--expected-voice-url"
        )

    expected_status_callback_url = None
    if args.expected_status_callback_url:
        expected_status_callback_url = validate_https_url(
            args.expected_status_callback_url,
            label="--expected-status-callback-url",
        )

    application_sid = None
    if args.application_sid:
        application_sid = validate_application_sid(
            args.application_sid, label="--application-sid"
        )

    application = _find_application(client, application_sid, args.friendly_name)
    application_result = {
        "checked": True,
        "found": application is not None,
        "sid": application.get("sid") if application else None,
        "sid_redacted": redact_sid(application.get("sid") if application else None),
        "friendly_name": application.get("friendly_name") if application else None,
        "voice_url": application.get("voice_url") if application else None,
        "voice_method": application.get("voice_method") if application else None,
        "status_callback_url": application.get("status_callback") if application else None,
    }
    if expected_voice_url:
        application_result["expected_voice_url"] = expected_voice_url
        application_result["voice_url_ok"] = (
            application is not None and application.get("voice_url") == expected_voice_url
        )
    if expected_status_callback_url:
        application_result["expected_status_callback_url"] = expected_status_callback_url
        application_result["status_callback_url_ok"] = (
            application is not None
            and application.get("status_callback") == expected_status_callback_url
        )
    result["application"] = application_result
    if application is None:
        result["ok"] = False
    if application_result.get("voice_url_ok") is False:
        result["ok"] = False
    if application_result.get("status_callback_url_ok") is False:
        result["ok"] = False

    phone_number = None
    if args.phone_number:
        phone_number = validate_e164(args.phone_number, label="--phone-number")

    if phone_number:
        phone_result = _find_phone_number(
            client=client,
            phone_number=phone_number,
            expected_application_sid=application.get("sid") if application else None,
        )
        result["phone_number"] = phone_result
        if not phone_result["ok"]:
            result["ok"] = False

    return result


def _find_application(
    client: TwilioClient, application_sid: str | None, friendly_name: str
) -> dict[str, Any] | None:
    if application_sid:
        return client.get_application(application_sid)

    matches = client.list_applications(friendly_name=friendly_name)
    if len(matches) > 1:
        redacted = ", ".join(redact_sid(item.get("sid")) for item in matches)
        raise TwilioScriptError(
            f"Multiple TwiML Apps match friendly name {friendly_name!r}: {redacted}."
        )
    return matches[0] if matches else None


def _find_phone_number(
    *,
    client: TwilioClient,
    phone_number: str,
    expected_application_sid: str | None,
) -> dict[str, Any]:
    matches = client.list_incoming_phone_numbers(phone_number=phone_number)
    if not matches:
        return {
            "checked": True,
            "ok": False,
            "requested": phone_number,
            "found": False,
            "reason": "phone number not found in this Twilio account",
        }
    if len(matches) > 1:
        redacted = ", ".join(redact_sid(item.get("sid")) for item in matches)
        raise TwilioScriptError(f"Multiple phone resources matched {phone_number}: {redacted}.")

    phone = matches[0]
    actual_application_sid = phone.get("voice_application_sid") or None
    attached = bool(
        expected_application_sid and actual_application_sid == expected_application_sid
    )
    return {
        "checked": True,
        "ok": attached,
        "requested": phone_number,
        "found": True,
        "sid": phone.get("sid"),
        "sid_redacted": redact_sid(phone.get("sid")),
        "voice_application_sid": actual_application_sid,
        "expected_voice_application_sid": expected_application_sid,
    }


def print_text_summary(result: dict[str, Any]) -> None:
    print("Twilio verification summary")
    print(f"- Account SID suffix: {result['account']['sid_suffix']}")
    print(f"- Credential validation: {result['credential_validation']}")

    app = result["application"]
    if app["checked"]:
        print(f"- TwiML App found: {app['found']}")
        print(f"- TwiML App SID: {app.get('sid') or '(not found)'}")
        print(f"- Voice URL: {app.get('voice_url') or '(not set)'}")
        if "voice_url_ok" in app:
            print(f"- Voice URL ok: {app['voice_url_ok']}")
        print(
            f"- Status callback URL: {app.get('status_callback_url') or '(not set)'}"
        )
        if "status_callback_url_ok" in app:
            print(f"- Status callback URL ok: {app['status_callback_url_ok']}")
        print(f"- Voice method: {app.get('voice_method') or '(not set)'}")
    else:
        print("- TwiML App check: skipped")

    phone = result["phone_number"]
    if phone["checked"]:
        print(f"- Phone number found: {phone['found']}")
        print(f"- Phone routing ok: {phone['ok']}")
        print(f"- Phone resource SID: {phone.get('sid') or '(not found)'}")
    else:
        print("- Phone number check: skipped")

    print("- ConversationRelay: unknown until checked in Twilio Console/account settings")
    print("- Gather fallback: available through standard Twilio Voice")
    print(f"- Overall ok: {result['ok']}")


if __name__ == "__main__":
    raise SystemExit(main())
