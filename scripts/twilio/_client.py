"""Shared Twilio REST helpers for local provisioning scripts."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

API_BASE_URL = "https://api.twilio.com"
USER_AGENT = "shs-ai-agent-twilio-scripts/0.1"

ACCOUNT_SID_RE = re.compile(r"^AC[0-9a-fA-F]{32}$")
APPLICATION_SID_RE = re.compile(r"^AP[0-9a-fA-F]{32}$")
PHONE_NUMBER_SID_RE = re.compile(r"^PN[0-9a-fA-F]{32}$")
E164_RE = re.compile(r"^\+[1-9][0-9]{1,14}$")

Transport = Callable[
    [str, str, dict[str, str], bytes | None],
    tuple[int, dict[str, Any] | str | bytes | None],
]


class TwilioScriptError(RuntimeError):
    """Base error for Twilio provisioning scripts."""


class MissingTwilioConfig(TwilioScriptError):
    """Raised when required Twilio credentials are absent."""


class TwilioApiError(TwilioScriptError):
    """Raised when Twilio returns an unsuccessful response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class TwilioConfig:
    """Runtime Twilio credentials.

    Only the account SID and auth token are required for these setup scripts.
    API keys are intentionally not written or managed by this code path.
    """

    account_sid: str
    auth_token: str

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, *, validate_sid: bool = True
    ) -> TwilioConfig:
        source = os.environ if env is None else env
        account_sid = source.get("TWILIO_ACCOUNT_SID", "").strip()
        auth_token = source.get("TWILIO_AUTH_TOKEN", "").strip()

        missing = [
            name
            for name, value in {
                "TWILIO_ACCOUNT_SID": account_sid,
                "TWILIO_AUTH_TOKEN": auth_token,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise MissingTwilioConfig(f"Missing required environment: {joined}")

        if validate_sid and not ACCOUNT_SID_RE.fullmatch(account_sid):
            raise MissingTwilioConfig(
                "TWILIO_ACCOUNT_SID must look like AC followed by 32 hex chars."
            )

        return cls(account_sid=account_sid, auth_token=auth_token)


def redact_account_sid(account_sid: str | None) -> str:
    """Return only a non-sensitive suffix for the account SID."""

    if not account_sid:
        return "(not set)"
    return f"...{account_sid[-6:]}"


def redact_sid(sid: str | None) -> str:
    """Redact a Twilio SID while leaving enough context for debugging."""

    if not sid:
        return "(not set)"
    if len(sid) <= 8:
        return "***"
    return f"{sid[:2]}...{sid[-6:]}"


def validate_https_url(value: str, *, label: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise TwilioScriptError(f"{label} must be an absolute https:// URL.")
    return value


def validate_e164(value: str, *, label: str = "phone number") -> str:
    if not E164_RE.fullmatch(value):
        raise TwilioScriptError(
            f"{label} must be in E.164 format, for example +14155551234."
        )
    return value


def validate_application_sid(value: str, *, label: str = "application SID") -> str:
    if not APPLICATION_SID_RE.fullmatch(value):
        raise TwilioScriptError(f"{label} must look like AP followed by 32 hex chars.")
    return value


def validate_phone_number_sid(value: str, *, label: str = "phone number SID") -> str:
    if not PHONE_NUMBER_SID_RE.fullmatch(value):
        raise TwilioScriptError(f"{label} must look like PN followed by 32 hex chars.")
    return value


def _normalize_params(params: Mapping[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            normalized[key] = "true" if value else "false"
        else:
            normalized[key] = str(value)
    return normalized


def _parse_error_message(raw_body: bytes) -> str:
    if not raw_body:
        return "Twilio request failed with an empty response body."
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return raw_body.decode("utf-8", errors="replace")
    message = payload.get("message") or payload.get("error") or payload
    return str(message)


def _default_transport(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, dict[str, Any] | str | bytes | None]:
    request = urllib.request.Request(  # noqa: S310
        url, data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            raw_body = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raise TwilioApiError(error.code, _parse_error_message(error.read())) from error
    except urllib.error.URLError as error:
        raise TwilioApiError(0, f"Twilio request failed: {error.reason}") from error

    if not raw_body:
        return status, {}

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = raw_body.decode("utf-8", errors="replace")
    return status, payload


class TwilioClient:
    """Small Twilio REST client for the scripts.

    The client deliberately covers only the resources needed in Phase 0.5:
    TwiML Applications, incoming phone number association, and available-number
    search. Backend runtime code can use the official SDK later.
    """

    def __init__(
        self, config: TwilioConfig, *, transport: Transport | None = None
    ) -> None:
        self._config = config
        self._transport = transport or _default_transport

    @property
    def account_sid(self) -> str:
        return self._config.account_sid

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        form: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not path.startswith("/"):
            path = f"/{path}"

        url = f"{API_BASE_URL}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(_normalize_params(query))}"

        body: bytes | None = None
        headers = {
            "Accept": "application/json",
            "Authorization": self._authorization_header(),
            "User-Agent": USER_AGENT,
        }

        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = urllib.parse.urlencode(_normalize_params(form)).encode("utf-8")

        status, payload = self._transport(method.upper(), url, headers, body)
        if status >= 400:
            raise TwilioApiError(status, f"Twilio request failed with HTTP {status}.")
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise TwilioApiError(status, "Twilio response was not a JSON object.")
        return payload

    def validate_credentials(self) -> None:
        self.list_applications(page_size=1)

    def get_application(self, application_sid: str) -> dict[str, Any]:
        validate_application_sid(application_sid)
        path = self._account_path(f"Applications/{application_sid}.json")
        return self.request("GET", path)

    def list_applications(
        self, *, friendly_name: str | None = None, page_size: int = 20
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"PageSize": page_size}
        if friendly_name:
            query["FriendlyName"] = friendly_name
        payload = self.request("GET", self._account_path("Applications.json"), query=query)
        return list(payload.get("applications", []))

    def create_application(
        self,
        *,
        friendly_name: str,
        voice_url: str,
        status_callback_url: str | None = None,
    ) -> dict[str, Any]:
        form: dict[str, Any] = {
            "FriendlyName": friendly_name,
            "VoiceMethod": "POST",
            "VoiceUrl": voice_url,
        }
        if status_callback_url:
            form["StatusCallback"] = status_callback_url
            form["StatusCallbackMethod"] = "POST"
        return self.request("POST", self._account_path("Applications.json"), form=form)

    def update_application(
        self,
        application_sid: str,
        *,
        friendly_name: str | None = None,
        voice_url: str,
        status_callback_url: str | None = None,
    ) -> dict[str, Any]:
        validate_application_sid(application_sid)
        form: dict[str, Any] = {
            "VoiceMethod": "POST",
            "VoiceUrl": voice_url,
        }
        if friendly_name:
            form["FriendlyName"] = friendly_name
        if status_callback_url:
            form["StatusCallback"] = status_callback_url
            form["StatusCallbackMethod"] = "POST"
        path = self._account_path(f"Applications/{application_sid}.json")
        return self.request("POST", path, form=form)

    def list_incoming_phone_numbers(
        self, *, phone_number: str | None = None, page_size: int = 20
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"PageSize": page_size}
        if phone_number:
            query["PhoneNumber"] = phone_number
        payload = self.request(
            "GET", self._account_path("IncomingPhoneNumbers.json"), query=query
        )
        return list(payload.get("incoming_phone_numbers", []))

    def update_incoming_phone_number_application(
        self, phone_number_sid: str, *, application_sid: str
    ) -> dict[str, Any]:
        validate_phone_number_sid(phone_number_sid)
        validate_application_sid(application_sid)
        path = self._account_path(f"IncomingPhoneNumbers/{phone_number_sid}.json")
        return self.request("POST", path, form={"VoiceApplicationSid": application_sid})

    def list_available_local_numbers(
        self,
        *,
        country_code: str,
        area_code: str | None = None,
        contains: str | None = None,
        in_region: str | None = None,
        limit: int = 10,
        exclude_address_required: bool = True,
    ) -> list[dict[str, Any]]:
        clean_country = country_code.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", clean_country):
            raise TwilioScriptError("country code must be a two-letter ISO code.")
        if limit < 1 or limit > 100:
            raise TwilioScriptError("limit must be between 1 and 100.")

        query: dict[str, Any] = {
            "VoiceEnabled": True,
            "PageSize": limit,
        }
        if area_code:
            query["AreaCode"] = area_code
        if contains:
            query["Contains"] = contains
        if in_region:
            query["InRegion"] = in_region
        if exclude_address_required:
            query["ExcludeAllAddressRequired"] = True

        path = self._account_path(f"AvailablePhoneNumbers/{clean_country}/Local.json")
        payload = self.request("GET", path, query=query)
        return list(payload.get("available_phone_numbers", []))

    def _account_path(self, resource: str) -> str:
        return f"/2010-04-01/Accounts/{self.account_sid}/{resource}"

    def _authorization_header(self) -> str:
        token = f"{self._config.account_sid}:{self._config.auth_token}".encode()
        return f"Basic {base64.b64encode(token).decode('ascii')}"
