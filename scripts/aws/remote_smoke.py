#!/usr/bin/env python3
"""Remote smoke tests for the deployed SHS AI Agent stack."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

MAX_RESPONSE_BYTES = 1_000_000
USER_AGENT = "shs-ai-agent-remote-smoke/1.0"


class SmokeError(RuntimeError):
    """Raised when a remote smoke check fails."""


@dataclass(frozen=True)
class FetchResult:
    """HTTP response data used by smoke checks."""

    url: str
    status: int
    body: bytes
    content_type: str

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


Fetch = Callable[[str, float], FetchResult]


def normalize_base_url(value: str, *, label: str) -> str:
    """Validate and normalize a base URL."""

    parsed = urllib.parse.urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SmokeError(f"{label} must be an absolute http(s) URL.")
    return value.strip().rstrip("/")


def join_url(base_url: str, path: str) -> str:
    """Join a normalized base URL and an absolute path."""

    return f"{base_url}/{path.lstrip('/')}"


def fetch_url(url: str, timeout: float) -> FetchResult:
    """Fetch a URL with conservative response limits."""

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SmokeError(f"{url} must use http or https.")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise SmokeError(f"{url} returned more than {MAX_RESPONSE_BYTES} bytes.")
            return FetchResult(
                url=url,
                status=response.status,
                body=body,
                content_type=response.headers.get("content-type", ""),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(4096)
        snippet = body.decode("utf-8", errors="replace").strip()
        raise SmokeError(f"{url} returned HTTP {exc.code}: {snippet}") from exc
    except urllib.error.URLError as exc:
        raise SmokeError(f"{url} could not be reached: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SmokeError(f"{url} timed out.") from exc


def require_success(result: FetchResult) -> None:
    if result.status < 200 or result.status >= 300:
        raise SmokeError(f"{result.url} returned HTTP {result.status}.")


def check_api_health(api_base_url: str, timeout: float, fetch: Fetch = fetch_url) -> dict[str, Any]:
    """Check the backend health endpoint."""

    url = join_url(api_base_url, "/healthz")
    result = fetch(url, timeout)
    require_success(result)
    try:
        payload = json.loads(result.text())
    except json.JSONDecodeError as exc:
        raise SmokeError(f"{url} did not return valid JSON.") from exc

    if payload.get("status") != "ok":
        raise SmokeError(f"{url} returned unhealthy status: {payload.get('status')!r}.")
    if payload.get("service") != "shs-ai-agent-backend":
        raise SmokeError(f"{url} returned unexpected service: {payload.get('service')!r}.")

    return {
        "check": "api_health",
        "url": url,
        "status": result.status,
        "environment": payload.get("environment"),
    }


def check_frontend_shell(
    frontend_base_url: str,
    timeout: float,
    fetch: Fetch = fetch_url,
) -> dict[str, Any]:
    """Check the deployed frontend HTML shell."""

    url = join_url(frontend_base_url, "/")
    result = fetch(url, timeout)
    require_success(result)
    html = result.text()
    if 'id="root"' not in html or "Sears Home Services AI Agent" not in html:
        raise SmokeError(f"{url} did not return the expected frontend shell.")

    return {
        "check": "frontend_shell",
        "url": url,
        "status": result.status,
        "content_type": result.content_type,
    }


def check_frontend_upload_route(
    frontend_base_url: str,
    timeout: float,
    fetch: Fetch = fetch_url,
) -> dict[str, Any]:
    """Check CloudFront's SPA fallback for upload links."""

    url = join_url(frontend_base_url, "/uploads/remote-smoke-token")
    result = fetch(url, timeout)
    require_success(result)
    html = result.text()
    if 'id="root"' not in html:
        raise SmokeError(f"{url} did not return the frontend SPA shell.")

    return {
        "check": "frontend_upload_route",
        "url": url,
        "status": result.status,
        "content_type": result.content_type,
    }


def run_checks(api_base_url: str, frontend_base_url: str, timeout: float) -> list[dict[str, Any]]:
    normalized_api_url = normalize_base_url(api_base_url, label="--api-base-url")
    normalized_frontend_url = normalize_base_url(
        frontend_base_url,
        label="--frontend-base-url",
    )
    return [
        check_api_health(normalized_api_url, timeout),
        check_frontend_shell(normalized_frontend_url, timeout),
        check_frontend_upload_route(normalized_frontend_url, timeout),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run remote smoke checks against the deployed SHS AI Agent stack.",
    )
    parser.add_argument(
        "--api-base-url",
        required=True,
        help="Deployed API base URL, for example https://api.shs.buildrlab.com.",
    )
    parser.add_argument(
        "--frontend-base-url",
        required=True,
        help="Deployed frontend base URL, for example https://shs.buildrlab.com.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        checks = run_checks(
            api_base_url=args.api_base_url,
            frontend_base_url=args.frontend_base_url,
            timeout=args.timeout,
        )
    except SmokeError as exc:
        print(f"Remote smoke failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"ok": True, "checks": checks}, indent=2, sort_keys=True))
    else:
        print("Remote smoke summary")
        for check in checks:
            print(f"- {check['check']}: ok ({check['url']})")
        print("- Overall ok: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
