from __future__ import annotations

import argparse
import base64
import importlib.util
import os
import subprocess
import sys
import unittest
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TWILIO_DIR = REPO_ROOT / "scripts" / "twilio"
sys.path.insert(0, str(TWILIO_DIR))

from _client import (  # noqa: E402
    MissingTwilioConfig,
    TwilioClient,
    TwilioConfig,
    TwilioScriptError,
    redact_account_sid,
    validate_e164,
    validate_https_url,
)

ACCOUNT_SID = "AC" + ("a" * 32)
AUTH_TOKEN = "test-auth-token"  # noqa: S105


def _load_script_module(module_name: str, script_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, TWILIO_DIR / script_name)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load scripts/twilio/{script_name} for tests.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TWILIO_SETUP = _load_script_module("twilio_setup_script", "setup.py")
TWILIO_VERIFY = _load_script_module("twilio_verify_script", "verify.py")
TWILIO_SMOKE = _load_script_module("twilio_smoke_script", "smoke_server.py")


@contextmanager
def _twilio_env() -> Iterator[None]:
    original_account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    original_auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    try:
        os.environ["TWILIO_ACCOUNT_SID"] = ACCOUNT_SID
        os.environ["TWILIO_AUTH_TOKEN"] = AUTH_TOKEN
        yield
    finally:
        if original_account_sid is None:
            os.environ.pop("TWILIO_ACCOUNT_SID", None)
        else:
            os.environ["TWILIO_ACCOUNT_SID"] = original_account_sid
        if original_auth_token is None:
            os.environ.pop("TWILIO_AUTH_TOKEN", None)
        else:
            os.environ["TWILIO_AUTH_TOKEN"] = original_auth_token


class FakeTransport:
    def __init__(self, responses: list[tuple[int, dict[str, Any]]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, dict[str, Any]]:
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "body": body}
        )
        return self.responses.pop(0)


class TwilioClientTests(unittest.TestCase):
    def test_config_from_env_rejects_missing_values(self) -> None:
        with self.assertRaises(MissingTwilioConfig):
            TwilioConfig.from_env({})

    def test_config_from_env_rejects_bad_account_sid(self) -> None:
        with self.assertRaises(MissingTwilioConfig):
            TwilioConfig.from_env(
                {"TWILIO_ACCOUNT_SID": "bad", "TWILIO_AUTH_TOKEN": AUTH_TOKEN}
            )

    def test_validate_https_url_rejects_http(self) -> None:
        with self.assertRaises(TwilioScriptError):
            validate_https_url("http://example.com", label="test url")

    def test_validate_e164_normalizes_common_phone_formatting(self) -> None:
        self.assertEqual(
            validate_e164("+1 (737) 355-9397", label="--phone-number"),
            "+17373559397",
        )

    def test_validate_e164_rejects_numbers_without_country_prefix(self) -> None:
        with self.assertRaises(TwilioScriptError):
            validate_e164("7373559397", label="--phone-number")

    def test_redact_account_sid_exposes_suffix_only(self) -> None:
        self.assertEqual(redact_account_sid(ACCOUNT_SID), "...aaaaaa")

    def test_create_application_builds_authorized_form_request(self) -> None:
        transport = FakeTransport(
            [
                (
                    201,
                    {
                        "sid": "AP" + ("b" * 32),
                        "voice_url": "https://example.com/twilio/voice",
                    },
                )
            ]
        )
        client = TwilioClient(
            TwilioConfig(account_sid=ACCOUNT_SID, auth_token=AUTH_TOKEN),
            transport=transport,
        )

        client.create_application(
            friendly_name="SHS AI Agent",
            voice_url="https://example.com/twilio/voice",
            status_callback_url="https://example.com/twilio/status",
        )

        call = transport.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertIn(f"/Accounts/{ACCOUNT_SID}/Applications.json", call["url"])

        auth = call["headers"]["Authorization"].removeprefix("Basic ")
        decoded = base64.b64decode(auth).decode("utf-8")
        self.assertEqual(decoded, f"{ACCOUNT_SID}:{AUTH_TOKEN}")

        body = urllib.parse.parse_qs(call["body"].decode("utf-8"))
        self.assertEqual(body["FriendlyName"], ["SHS AI Agent"])
        self.assertEqual(body["VoiceMethod"], ["POST"])
        self.assertEqual(body["VoiceUrl"], ["https://example.com/twilio/voice"])
        self.assertEqual(
            body["StatusCallback"], ["https://example.com/twilio/status"]
        )
        self.assertNotIn(AUTH_TOKEN, call["body"].decode("utf-8"))

    def test_available_number_search_filters_for_voice(self) -> None:
        transport = FakeTransport([(200, {"available_phone_numbers": []})])
        client = TwilioClient(
            TwilioConfig(account_sid=ACCOUNT_SID, auth_token=AUTH_TOKEN),
            transport=transport,
        )

        client.list_available_local_numbers(
            country_code="US", area_code="212", contains="555", limit=5
        )

        parsed = urllib.parse.urlparse(transport.calls[0]["url"])
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(query["VoiceEnabled"], ["true"])
        self.assertEqual(query["ExcludeAllAddressRequired"], ["true"])
        self.assertEqual(query["AreaCode"], ["212"])
        self.assertEqual(query["Contains"], ["555"])
        self.assertEqual(query["PageSize"], ["5"])


class TwilioScriptCliTests(unittest.TestCase):
    def test_scripts_support_help(self) -> None:
        for script_name in ("setup.py", "verify.py", "list_numbers.py", "smoke_server.py"):
            with self.subTest(script_name=script_name):
                result = subprocess.run(  # noqa: S603
                    [sys.executable, str(TWILIO_DIR / script_name), "--help"],
                    capture_output=True,
                    check=False,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_setup_dry_run_without_credentials_does_not_leak_env(self) -> None:
        env = {"PATH": os.environ.get("PATH", "")}
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(TWILIO_DIR / "setup.py"),
                "--voice-url",
                "https://example.com/twilio/voice",
                "--dry-run",
            ],
            capture_output=True,
            check=False,
            env=env,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped_missing_env_dry_run", result.stdout)
        self.assertNotIn("TWILIO_AUTH_TOKEN", result.stdout)


class TwilioSetupPlanTests(unittest.TestCase):
    def test_dry_run_can_plan_phone_attach_after_app_create(self) -> None:
        phone_sid = "PN" + ("c" * 32)
        transport = FakeTransport(
            [
                (200, {"applications": []}),
                (200, {"applications": []}),
                (
                    200,
                    {
                        "incoming_phone_numbers": [
                            {
                                "sid": phone_sid,
                                "phone_number": "+17373559397",
                                "voice_application_sid": "",
                            }
                        ]
                    },
                ),
            ]
        )
        client = TwilioClient(
            TwilioConfig(account_sid=ACCOUNT_SID, auth_token=AUTH_TOKEN),
            transport=transport,
        )

        original_load_config = TWILIO_SETUP._load_config
        original_client_class = TWILIO_SETUP.TwilioClient
        try:
            TWILIO_SETUP._load_config = lambda _dry_run: TwilioConfig(
                account_sid=ACCOUNT_SID, auth_token=AUTH_TOKEN
            )
            TWILIO_SETUP.TwilioClient = lambda _config: client

            result = TWILIO_SETUP.run(
                argparse.Namespace(
                    friendly_name="SHS AI Agent",
                    voice_url="https://api.shs.buildrlab.com/twilio/voice/incoming",
                    status_callback_url=(
                        "https://api.shs.buildrlab.com/twilio/voice/status"
                    ),
                    phone_number="+1 737 355 9397",
                    application_sid=None,
                    dry_run=True,
                    json=False,
                )
            )
        finally:
            TWILIO_SETUP._load_config = original_load_config
            TWILIO_SETUP.TwilioClient = original_client_class

        self.assertEqual(result["application"]["action"], "would_create")
        self.assertEqual(
            result["phone_number"]["action"], "would_attach_after_app_create"
        )
        self.assertEqual(result["phone_number"]["requested"], "+17373559397")
        self.assertEqual(result["phone_number"]["sid"], phone_sid)


class TwilioVerifyPlanTests(unittest.TestCase):
    def test_verify_checks_expected_urls_and_phone_routing(self) -> None:
        application_sid = "AP" + ("b" * 32)
        phone_sid = "PN" + ("c" * 32)
        voice_url = "https://api.shs.buildrlab.com/twilio/voice/incoming"
        status_callback_url = "https://api.shs.buildrlab.com/twilio/voice/status"
        transport = FakeTransport(
            [
                (200, {"applications": []}),
                (
                    200,
                    {
                        "applications": [
                            {
                                "sid": application_sid,
                                "friendly_name": "SHS AI Agent",
                                "voice_url": voice_url,
                                "voice_method": "POST",
                                "status_callback": status_callback_url,
                            }
                        ]
                    },
                ),
                (
                    200,
                    {
                        "incoming_phone_numbers": [
                            {
                                "sid": phone_sid,
                                "phone_number": "+17373559397",
                                "voice_application_sid": application_sid,
                            }
                        ]
                    },
                ),
            ]
        )
        client = TwilioClient(
            TwilioConfig(account_sid=ACCOUNT_SID, auth_token=AUTH_TOKEN),
            transport=transport,
        )

        original_client_class = TWILIO_VERIFY.TwilioClient
        try:
            TWILIO_VERIFY.TwilioClient = lambda _config: client

            with _twilio_env():
                result = TWILIO_VERIFY.run(
                    argparse.Namespace(
                        friendly_name="SHS AI Agent",
                        application_sid=None,
                        phone_number="+1 737 355 9397",
                        expected_voice_url=voice_url,
                        expected_status_callback_url=status_callback_url,
                        credentials_only=False,
                        json=False,
                    )
                )
        finally:
            TWILIO_VERIFY.TwilioClient = original_client_class

        self.assertTrue(result["ok"])
        self.assertTrue(result["application"]["voice_url_ok"])
        self.assertTrue(result["application"]["status_callback_url_ok"])
        self.assertTrue(result["phone_number"]["ok"])

    def test_verify_fails_on_expected_voice_url_mismatch(self) -> None:
        application_sid = "AP" + ("b" * 32)
        transport = FakeTransport(
            [
                (200, {"applications": []}),
                (
                    200,
                    {
                        "applications": [
                            {
                                "sid": application_sid,
                                "friendly_name": "SHS AI Agent",
                                "voice_url": "https://example.com/wrong",
                                "voice_method": "POST",
                                "status_callback": (
                                    "https://api.shs.buildrlab.com/twilio/voice/status"
                                ),
                            }
                        ]
                    },
                ),
            ]
        )
        client = TwilioClient(
            TwilioConfig(account_sid=ACCOUNT_SID, auth_token=AUTH_TOKEN),
            transport=transport,
        )

        original_client_class = TWILIO_VERIFY.TwilioClient
        try:
            TWILIO_VERIFY.TwilioClient = lambda _config: client

            with _twilio_env():
                result = TWILIO_VERIFY.run(
                    argparse.Namespace(
                        friendly_name="SHS AI Agent",
                        application_sid=None,
                        phone_number=None,
                        expected_voice_url=(
                            "https://api.shs.buildrlab.com/twilio/voice/incoming"
                        ),
                        expected_status_callback_url=None,
                        credentials_only=False,
                        json=False,
                    )
                )
        finally:
            TWILIO_VERIFY.TwilioClient = original_client_class

        self.assertFalse(result["ok"])
        self.assertFalse(result["application"]["voice_url_ok"])


class TwilioSmokeServerTests(unittest.TestCase):
    def test_smoke_twiml_uses_gather_fallback(self) -> None:
        twiml = TWILIO_SMOKE.build_voice_twiml(
            "Sears Home Services smoke test & diagnostics"
        )

        self.assertIn("<Gather", twiml)
        self.assertIn('input="speech dtmf"', twiml)
        self.assertIn('action="/twilio/voice/gather"', twiml)
        self.assertIn("smoke test &amp; diagnostics", twiml)
        self.assertIn("<Hangup/>", twiml)

    def test_smoke_server_redacts_sensitive_twilio_fields(self) -> None:
        redacted = TWILIO_SMOKE.redact_form(
            {
                "AccountSid": "AC" + ("a" * 32),
                "CallSid": "CA" + ("b" * 32),
                "From": "+17373559397",
                "To": "+14155551234",
                "SpeechResult": "washer is leaking",
            }
        )

        self.assertEqual(redacted["AccountSid"], "AC...aaaaaa")
        self.assertEqual(redacted["CallSid"], "CA...bbbbbb")
        self.assertEqual(redacted["From"], "+...9397")
        self.assertEqual(redacted["To"], "+...1234")
        self.assertEqual(redacted["SpeechResult"], "washer is leaking")

    def test_smoke_server_parses_urlencoded_form(self) -> None:
        body = b"CallSid=CA123&SpeechResult=test+call"
        parsed = TWILIO_SMOKE.parse_form_body(
            content_type="application/x-www-form-urlencoded",
            content_length=str(len(body)),
            body=body,
        )

        self.assertEqual(parsed["CallSid"], "CA123")
        self.assertEqual(parsed["SpeechResult"], "test call")


if __name__ == "__main__":
    unittest.main()
