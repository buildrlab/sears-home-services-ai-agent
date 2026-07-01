#!/usr/bin/env python3
"""Final live AWS smoke checks for reviewer readiness."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)
USER_AGENT = "shs-ai-agent-final-live-smoke/1.0"


class FinalSmokeError(RuntimeError):
    """Raised when final live smoke validation fails."""


class HttpFinalSmokeError(FinalSmokeError):
    """Raised for non-success HTTP responses."""

    def __init__(self, url: str, status: int, body: str) -> None:
        super().__init__(f"{url} returned HTTP {status}: {body}")
        self.url = url
        self.status = status
        self.body = body


@dataclass(frozen=True)
class CheckResult:
    name: str
    detail: str


@dataclass(frozen=True)
class HttpResult:
    url: str
    status: int
    body: bytes
    content_type: str

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.text())
        except json.JSONDecodeError as exc:
            raise FinalSmokeError(f"{self.url} did not return valid JSON.") from exc
        if not isinstance(payload, dict):
            raise FinalSmokeError(f"{self.url} returned JSON that is not an object.")
        return payload


class HttpClient:
    def __init__(self, api_base_url: str, timeout: float) -> None:
        self.api_base_url = normalize_base_url(api_base_url, label="--api-base-url")
        self.timeout = timeout

    def get_json(self, path: str) -> dict[str, Any]:
        return self._request("GET", join_url(self.api_base_url, path)).json()

    def post_json(self, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            join_url(self.api_base_url, path),
            body=json.dumps(payload or {}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        ).json()

    def post_form(
        self,
        path: str,
        payload: Mapping[str, str],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        return self._request(
            "POST",
            join_url(self.api_base_url, path),
            body=urllib.parse.urlencode(payload).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded", **dict(headers or {})},
        ).text()

    def post_multipart_url(
        self,
        url: str,
        fields: Mapping[str, str],
        *,
        filename: str,
        content_type: str,
        body: bytes,
    ) -> None:
        multipart_body, multipart_content_type = build_multipart_body(
            fields,
            filename=filename,
            content_type=content_type,
            body=body,
        )
        self._request(
            "POST",
            normalize_base_url(url, label="presigned upload url"),
            body=multipart_body,
            headers={"Content-Type": multipart_content_type},
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResult:
        request = urllib.request.Request(  # noqa: S310
            url,
            data=body,
            headers={"User-Agent": USER_AGENT, **dict(headers or {})},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return HttpResult(
                    url=url,
                    status=response.status,
                    body=response.read(),
                    content_type=response.headers.get("content-type", ""),
                )
        except urllib.error.HTTPError as exc:
            response_body = exc.read(4096).decode("utf-8", errors="replace")
            raise HttpFinalSmokeError(url, exc.code, response_body) from exc
        except urllib.error.URLError as exc:
            raise FinalSmokeError(f"{url} could not be reached: {exc.reason}") from exc
        except TimeoutError as exc:
            raise FinalSmokeError(f"{url} timed out.") from exc


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def run_live_smoke(
    *,
    api_base_url: str,
    email_to: str,
    twilio_auth_token: str,
    timeout: float,
) -> list[CheckResult]:
    client = HttpClient(api_base_url, timeout=timeout)
    checks: list[CheckResult] = []

    health = client.get_json("/healthz")
    require_equal(health.get("status"), "ok", "health status")
    require_equal(health.get("service"), "shs-ai-agent-backend", "health service")
    checks.append(CheckResult("api_health", str(health.get("environment"))))

    diagnostic_session = client.post_json(
        "/diagnostics/sessions",
        {
            "customer_name": "Final AWS Smoke",
            "customer_email": email_to,
            "customer_phone": "+15550100001",
        },
    )
    session_id = int(diagnostic_session["id"])
    checks.append(CheckResult("diagnostic_session_created", f"session={session_id}"))

    client.post_json(
        f"/diagnostics/sessions/{session_id}/turn",
        {"message": "My refrigerator is not cooling and there is water on the floor."},
    )
    diagnostic_turn = client.post_json(
        f"/diagnostics/sessions/{session_id}/turn",
        {"message": "The appliance is in 75201 and I want to schedule service."},
    )
    require_equal(diagnostic_turn["session"].get("zip_code"), "75201", "diagnostic ZIP")
    checks.append(CheckResult("tier1_diagnostic_flow", str(diagnostic_turn["session"]["status"])))

    call_sid = f"CAFNL{session_id}"
    incoming_twiml = post_signed_twilio_form(
        client,
        "/twilio/voice/incoming",
        {
            "CallSid": call_sid,
            "From": "+15550100001",
            "To": "+17373559397",
            "CallStatus": "ringing",
        },
        auth_token=twilio_auth_token,
    )
    if "<Gather" not in incoming_twiml and "<Connect" not in incoming_twiml:
        raise FinalSmokeError("Signed Twilio incoming webhook did not return TwiML.")

    gather_twiml = post_signed_twilio_form(
        client,
        "/twilio/voice/gather",
        {
            "CallSid": call_sid,
            "From": "+15550100001",
            "To": "+17373559397",
            "SpeechResult": "My refrigerator is not cooling in 75201.",
            "CallStatus": "in-progress",
        },
        auth_token=twilio_auth_token,
    )
    if "<Gather" not in gather_twiml:
        raise FinalSmokeError("Signed Twilio Gather webhook did not return Gather TwiML.")

    post_signed_twilio_form(
        client,
        "/twilio/voice/status",
        {
            "CallSid": call_sid,
            "From": "+15550100001",
            "To": "+17373559397",
            "CallStatus": "completed",
        },
        auth_token=twilio_auth_token,
    )
    checks.append(CheckResult("twilio_signed_webhooks", "ok"))

    upload_link = client.post_json(
        f"/diagnostics/sessions/{session_id}/upload-link",
        {"email": email_to},
    )
    if upload_link.get("email_sent") is not True:
        raise FinalSmokeError("SES upload-link send was not accepted by the backend.")
    token = extract_upload_token(str(upload_link["upload_url"]))
    checks.append(CheckResult("ses_upload_email_accepted", redact_email(email_to)))

    upload_record = client.get_json(f"/uploads/{token}")
    require_equal(upload_record.get("status"), "pending_upload", "upload token status")

    metadata = {
        "filename": "final-aws-smoke.png",
        "content_type": "image/png",
        "byte_size": len(PNG_1X1),
    }
    presigned = client.post_json(f"/uploads/{token}/presigned-post", metadata)
    client.post_multipart_url(
        str(presigned["url"]),
        presigned["fields"],
        filename=metadata["filename"],
        content_type=metadata["content_type"],
        body=PNG_1X1,
    )
    checks.append(CheckResult("tier3_object_uploaded", str(presigned["storage_key"])))

    completed = client.post_json(f"/uploads/{token}/complete", metadata)
    upload_id = int(completed["id"])
    require_equal(completed.get("status"), "analysis_pending", "completed upload status")

    analyzed = client.post_json(f"/diagnostics/uploads/{upload_id}/analysis")
    if analyzed.get("status") != "analyzed":
        raise FinalSmokeError(
            "Image analysis did not complete: "
            f"status={analyzed.get('status')!r} failure={analyzed.get('failure_reason')!r}"
        )
    if not analyzed.get("analysis_summary"):
        raise FinalSmokeError("Image analysis completed without a summary.")
    checks.append(CheckResult("tier3_image_analysis", str(analyzed["analysis_summary"])[:160]))

    final_session = client.get_json(f"/diagnostics/sessions/{session_id}")
    event_names = {
        event.get("tool_name")
        for event in final_session.get("events", [])
        if isinstance(event, dict)
    }
    if "analyze_image" not in event_names:
        raise FinalSmokeError("Diagnostic session did not record analyze_image event.")
    checks.append(CheckResult("session_history_contains_analysis", f"events={len(event_names)}"))

    return checks


def post_signed_twilio_form(
    client: HttpClient,
    path: str,
    payload: Mapping[str, str],
    *,
    auth_token: str,
) -> str:
    url = join_url(client.api_base_url, path)
    signature = build_twilio_signature(url, payload, auth_token)
    return client.post_form(path, payload, headers={"X-Twilio-Signature": signature})


def build_twilio_signature(url: str, params: Mapping[str, str], auth_token: str) -> str:
    signed = url + "".join(f"{key}{value}" for key, value in sorted(params.items()))
    digest = hmac.new(auth_token.encode(), signed.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def get_secret_with_aws_cli(
    *,
    secret_id: str,
    profile: str | None,
    region: str,
    runner: CommandRunner = subprocess.run,
) -> str:
    command = [
        "aws",
        "secretsmanager",
        "get-secret-value",
        "--secret-id",
        secret_id,
        "--region",
        region,
        "--query",
        "SecretString",
        "--output",
        "text",
    ]
    if profile:
        command.extend(["--profile", profile])
    result = runner(command, capture_output=True, check=False, text=True)
    if result.returncode != 0:
        raise FinalSmokeError("Could not retrieve Twilio auth token from AWS Secrets Manager.")
    secret = result.stdout.strip()
    if not secret:
        raise FinalSmokeError("AWS Secrets Manager returned an empty Twilio auth token.")
    return secret


def normalize_base_url(value: str, *, label: str) -> str:
    parsed = urllib.parse.urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise FinalSmokeError(f"{label} must be an absolute http(s) URL.")
    return value.strip().rstrip("/")


def join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def extract_upload_token(upload_url: str) -> str:
    parsed = urllib.parse.urlparse(upload_url)
    token = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    if not token:
        raise FinalSmokeError("Upload URL did not contain a token.")
    return token


def build_multipart_body(
    fields: Mapping[str, str],
    *,
    filename: str,
    content_type: str,
    body: bytes,
) -> tuple[bytes, str]:
    boundary = "----shs-final-smoke-boundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode(),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{filename}"\r\n'
            ).encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            body,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def redact_email(email: str) -> str:
    local, separator, domain = email.partition("@")
    if not separator:
        return "[redacted]"
    return f"{local[:2]}...@{domain}"


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise FinalSmokeError(f"Unexpected {label}: expected {expected!r}, got {actual!r}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run final live AWS reviewer checks against the deployed SHS AI Agent. "
            "This creates disposable diagnostic/upload records and uploads a tiny PNG."
        ),
    )
    parser.add_argument(
        "--api-base-url",
        default="https://api.shs.buildrlab.com",
        help="Deployed backend API base URL.",
    )
    parser.add_argument(
        "--email-to",
        default="no-reply@shs.buildrlab.com",
        help=(
            "Recipient for SES upload-link delivery. In SES sandbox this must be "
            "a verified email/domain recipient."
        ),
    )
    parser.add_argument(
        "--twilio-secret-id",
        default="/sears-home-services-ai-agent-prod/twilio-auth-token",
        help="AWS Secrets Manager secret ID for the Twilio auth token.",
    )
    parser.add_argument(
        "--aws-profile",
        default=os.environ.get("AWS_PROFILE"),
        help="Optional AWS CLI profile used to read the Twilio auth token.",
    )
    parser.add_argument("--aws-region", default="us-east-1", help="AWS region.")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        twilio_auth_token = get_secret_with_aws_cli(
            secret_id=args.twilio_secret_id,
            profile=args.aws_profile,
            region=args.aws_region,
        )
        checks = run_live_smoke(
            api_base_url=args.api_base_url,
            email_to=args.email_to,
            twilio_auth_token=twilio_auth_token,
            timeout=args.timeout,
        )
    except FinalSmokeError as exc:
        print(f"Final live smoke failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {"ok": True, "checks": [check.__dict__ for check in checks]},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("Final live smoke summary")
        for check in checks:
            print(f"- {check.name}: {check.detail}")
        print("- Overall ok: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
