#!/usr/bin/env python3
"""Reviewer-facing local smoke test for the SHS AI Agent."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Protocol

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)
USER_AGENT = "shs-ai-agent-reviewer-smoke/1.0"


class SmokeError(RuntimeError):
    """Raised when the reviewer smoke flow fails."""


class HttpSmokeError(SmokeError):
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
            raise SmokeError(f"{self.url} did not return valid JSON.") from exc
        if not isinstance(payload, dict):
            raise SmokeError(f"{self.url} returned JSON that is not an object.")
        return payload


class ReviewerClient(Protocol):
    def get_json(self, path: str) -> dict[str, Any]:
        """GET a JSON API path."""

    def post_json(self, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """POST a JSON API path."""

    def post_form(self, path: str, payload: Mapping[str, str]) -> str:
        """POST URL-encoded form data and return response text."""

    def get_text_url(self, url: str) -> str:
        """GET an absolute URL and return response text."""

    def post_multipart_url(
        self,
        url: str,
        fields: Mapping[str, str],
        *,
        filename: str,
        content_type: str,
        body: bytes,
    ) -> None:
        """POST a multipart form to an absolute URL."""


class HttpReviewerClient:
    def __init__(self, api_base_url: str, timeout: float) -> None:
        self.api_base_url = normalize_base_url(api_base_url, label="--api-base-url")
        self.timeout = timeout

    def get_json(self, path: str) -> dict[str, Any]:
        return self._request_json("GET", join_url(self.api_base_url, path))

    def post_json(self, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload or {}).encode("utf-8")
        return self._request_json(
            "POST",
            join_url(self.api_base_url, path),
            body=body,
            headers={"Content-Type": "application/json"},
        )

    def post_form(self, path: str, payload: Mapping[str, str]) -> str:
        body = urllib.parse.urlencode(payload).encode("utf-8")
        result = self._request(
            "POST",
            join_url(self.api_base_url, path),
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return result.text()

    def get_text_url(self, url: str) -> str:
        return self._request("GET", normalize_absolute_url(url, label="url")).text()

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
            normalize_absolute_url(url, label="presigned upload url"),
            body=multipart_body,
            headers={"Content-Type": multipart_content_type},
        )

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._request(method, url, body=body, headers=headers).json()

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResult:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise SmokeError(f"{url} must use http or https.")

        request_headers = {"User-Agent": USER_AGENT, **dict(headers or {})}
        request = urllib.request.Request(  # noqa: S310
            url,
            data=body,
            headers=request_headers,
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
            raise HttpSmokeError(url, exc.code, response_body) from exc
        except urllib.error.URLError as exc:
            raise SmokeError(f"{url} could not be reached: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SmokeError(f"{url} timed out.") from exc


def normalize_base_url(value: str, *, label: str) -> str:
    parsed = urllib.parse.urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SmokeError(f"{label} must be an absolute http(s) URL.")
    return value.strip().rstrip("/")


def normalize_absolute_url(value: str, *, label: str) -> str:
    return normalize_base_url(value, label=label)


def join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def extract_upload_token(upload_url: str) -> str:
    parsed = urllib.parse.urlparse(upload_url)
    token = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    if not token:
        raise SmokeError("Upload URL did not contain a token.")
    return token


def build_multipart_body(
    fields: Mapping[str, str],
    *,
    filename: str,
    content_type: str,
    body: bytes,
) -> tuple[bytes, str]:
    boundary = f"----shs-reviewer-{secrets.token_hex(12)}"
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


def candidate_starts(
    availability: list[dict[str, Any]],
    *,
    duration_minutes: int,
    attempts_per_window: int = 90,
) -> list[datetime]:
    today = datetime.now(UTC).date()
    minute_seed = int(datetime.now(UTC).timestamp() // 60)
    candidates: list[datetime] = []
    for window in availability:
        start_time = parse_time(str(window["start_time"]))
        end_time = parse_time(str(window["end_time"]))
        day_of_week = int(window["day_of_week"])
        base_date = next_weekday(today, day_of_week)
        if base_date <= today + timedelta(days=2):
            base_date += timedelta(days=7)
        total_minutes = minutes_between(start_time, end_time)
        max_offset = max(0, total_minutes - duration_minutes)
        for attempt in range(min(attempts_per_window, max_offset + 1)):
            offset = (minute_seed + attempt) % (max_offset + 1)
            candidates.append(
                datetime.combine(base_date, start_time, tzinfo=UTC)
                + timedelta(minutes=offset)
            )
    return candidates


def parse_time(value: str) -> time:
    return time.fromisoformat(value)


def next_weekday(start: date, day_of_week: int) -> date:
    days_ahead = (day_of_week - start.weekday()) % 7
    return start + timedelta(days=days_ahead)


def minutes_between(start: time, end: time) -> int:
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    return end_minutes - start_minutes


def run_reviewer_smoke(
    client: ReviewerClient,
    *,
    frontend_base_url: str | None,
    upload_object: bool,
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    health = client.get_json("/healthz")
    require_equal(health.get("status"), "ok", "health status")
    require_equal(health.get("service"), "shs-ai-agent-backend", "health service")
    checks.append(CheckResult("api_health", str(health.get("environment"))))

    diagnostic_session = client.post_json(
        "/diagnostics/sessions",
        {
            "customer_name": "Reviewer Smoke",
            "customer_phone": "+15550100001",
        },
    )
    session_id = int(diagnostic_session["id"])
    checks.append(CheckResult("diagnostic_session_created", f"session={session_id}"))

    client.post_json(
        f"/diagnostics/sessions/{session_id}/turn",
        {"message": "My refrigerator is not cooling and leaking."},
    )
    second_turn = client.post_json(
        f"/diagnostics/sessions/{session_id}/turn",
        {"message": "It is in 75201 and I need help scheduling service."},
    )
    session = second_turn["session"]
    require_equal(session.get("appliance_type"), "refrigerator", "appliance type")
    require_equal(session.get("zip_code"), "75201", "ZIP code")
    if "not cooling" not in session.get("symptoms", []):
        raise SmokeError("Diagnostic session did not remember the not cooling symptom.")
    if not any(call["name"] == "find_technician_matches" for call in second_turn["tool_calls"]):
        raise SmokeError("Diagnostic flow did not emit find_technician_matches.")
    checks.append(CheckResult("tier1_diagnostic_flow", str(session.get("status"))))

    matches_payload = client.get_json(
        "/scheduling/matches?zip_code=75201&appliance_type=refrigerator"
    )
    matches = matches_payload.get("matches", [])
    if not matches:
        raise SmokeError("No technician matches returned for refrigerator in 75201.")
    technician = matches[0]
    checks.append(CheckResult("tier2_technician_match", str(technician["name"])))

    appointment = create_and_book_appointment(
        client,
        technician=technician,
        session_id=session_id,
    )
    checks.append(
        CheckResult(
            "tier2_appointment_booked",
            str(appointment.get("confirmation_code")),
        )
    )

    incoming_twiml = client.post_form(
        "/twilio/voice/incoming",
        {
            "CallSid": f"CAREVIEWER{session_id}",
            "From": "+15550100001",
            "To": "+17373559397",
        },
    )
    if "<Gather" not in incoming_twiml:
        raise SmokeError("Twilio incoming webhook did not return Gather TwiML.")
    gather_twiml = client.post_form(
        "/twilio/voice/gather",
        {
            "CallSid": f"CAREVIEWER{session_id}",
            "From": "+15550100001",
            "To": "+17373559397",
            "SpeechResult": "My refrigerator is not cooling in 75201.",
        },
    )
    if "<Gather" not in gather_twiml:
        raise SmokeError("Twilio Gather webhook did not return Gather TwiML.")
    checks.append(CheckResult("twilio_gather_fallback", "ok"))

    upload_link = client.post_json(
        f"/diagnostics/sessions/{session_id}/upload-link",
        {"email": "reviewer@example.test"},
    )
    token = extract_upload_token(str(upload_link["upload_url"]))
    checks.append(CheckResult("tier3_upload_link_created", f"upload={upload_link['id']}"))

    upload_record = client.get_json(f"/uploads/{token}")
    require_equal(upload_record.get("status"), "pending_upload", "upload token status")

    metadata = {
        "filename": "reviewer-fridge.png",
        "content_type": "image/png",
        "byte_size": len(PNG_1X1),
    }
    presigned = client.post_json(f"/uploads/{token}/presigned-post", metadata)
    if upload_object:
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
    require_equal(analyzed.get("status"), "analyzed", "analysis status")
    if not analyzed.get("analysis_summary"):
        raise SmokeError("Image analysis did not produce a summary.")
    checks.append(CheckResult("tier3_image_analysis", str(analyzed["analysis_summary"])))

    final_session = client.get_json(f"/diagnostics/sessions/{session_id}")
    if not any(event.get("tool_name") == "analyze_image" for event in final_session["events"]):
        raise SmokeError("Diagnostic session does not include analyze_image event.")
    checks.append(CheckResult("dashboard_data_available", f"events={len(final_session['events'])}"))

    if frontend_base_url:
        frontend_url = normalize_base_url(frontend_base_url, label="--frontend-base-url")
        frontend_html = client.get_text_url(frontend_url)
        if 'id="root"' not in frontend_html:
            raise SmokeError("Frontend root did not return the React shell.")
        upload_html = client.get_text_url(join_url(frontend_url, f"/uploads/{token}"))
        if 'id="root"' not in upload_html:
            raise SmokeError("Frontend upload route did not return the React shell.")
        checks.append(CheckResult("frontend_shell", frontend_url))

    return checks


def create_and_book_appointment(
    client: ReviewerClient,
    *,
    technician: Mapping[str, Any],
    session_id: int,
) -> dict[str, Any]:
    for scheduled_start in candidate_starts(
        list(technician["availability"]),
        duration_minutes=30,
    ):
        payload = {
            "customer": {
                "full_name": "Reviewer Smoke",
                "email": f"reviewer+{session_id}@example.test",
                "phone": "+15550100001",
            },
            "technician_id": technician["id"],
            "appliance_type": "refrigerator",
            "zip_code": "75201",
            "scheduled_start": scheduled_start.isoformat().replace("+00:00", "Z"),
            "duration_minutes": 30,
            "issue_summary": "Reviewer smoke test refrigerator is not cooling.",
        }
        try:
            hold = client.post_json("/appointments/holds", payload)
        except HttpSmokeError as exc:
            if exc.status == 409:
                continue
            raise
        booked = client.post_json(f"/appointments/{hold['id']}/book")
        require_equal(booked.get("status"), "booked", "appointment status")
        if not booked.get("confirmation_code"):
            raise SmokeError("Booked appointment did not include a confirmation code.")
        return booked
    raise SmokeError("Could not find an available reviewer smoke appointment slot.")


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise SmokeError(f"Unexpected {label}: expected {expected!r}, got {actual!r}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local reviewer smoke flow against a running SHS AI Agent backend. "
            "Start docker-compose services, run Alembic/seed, and start Uvicorn first."
        ),
    )
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8000",
        help="Running backend API base URL.",
    )
    parser.add_argument(
        "--frontend-base-url",
        default=None,
        help="Optional running frontend base URL for shell and upload-route checks.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout per request in seconds.",
    )
    parser.add_argument(
        "--skip-object-upload",
        action="store_true",
        help="Skip the actual presigned S3/MinIO multipart object upload.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    client = HttpReviewerClient(args.api_base_url, timeout=args.timeout)
    try:
        checks = run_reviewer_smoke(
            client,
            frontend_base_url=args.frontend_base_url,
            upload_object=not args.skip_object_upload,
        )
    except SmokeError as exc:
        print(f"Reviewer smoke failed: {exc}", file=sys.stderr)
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
        print("Reviewer local smoke summary")
        for check in checks:
            print(f"- {check.name}: {check.detail}")
        print("- Overall ok: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
