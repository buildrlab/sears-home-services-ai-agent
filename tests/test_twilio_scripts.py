from __future__ import annotations

import base64
import os
import subprocess
import sys
import unittest
import urllib.parse
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
    validate_https_url,
)

ACCOUNT_SID = "AC" + ("a" * 32)
AUTH_TOKEN = "test-auth-token"  # noqa: S105


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
        for script_name in ("setup.py", "verify.py", "list_numbers.py"):
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


if __name__ == "__main__":
    unittest.main()
