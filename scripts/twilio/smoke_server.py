#!/usr/bin/env python3
"""Local Twilio Voice smoke-test webhook.

This server is for Phase 0.5 live-call validation only. It is intentionally
standard-library based so Twilio routing can be tested before the backend exists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_EVENT_LOG = Path("/private/tmp/shs-twilio-smoke/events.jsonl")
VOICE_PATH = "/twilio/voice/incoming"
GATHER_PATH = "/twilio/voice/gather"
STATUS_PATH = "/twilio/voice/status"
HEALTH_PATH = "/healthz"
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
SID_RE = re.compile(r"^(AC|AP|CA|PN)[0-9a-fA-F]{32}$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local Twilio Voice smoke-test webhook for tunneled inbound "
            "call verification."
        )
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Bind port.")
    parser.add_argument(
        "--event-log",
        default=str(DEFAULT_EVENT_LOG),
        help="JSONL path for redacted inbound request events.",
    )
    parser.add_argument(
        "--message",
        default=(
            "Sears Home Services AI agent smoke test connected. "
            "Press any digit, or say test, after the tone."
        ),
        help="Message spoken by Twilio during the smoke call.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.port < 1 or args.port > 65535:
        print("error: --port must be between 1 and 65535.", file=sys.stderr)
        return 2

    event_log = Path(args.event_log).expanduser().resolve()
    event_log.parent.mkdir(parents=True, exist_ok=True)

    server = _build_server(
        host=args.host,
        port=args.port,
        event_log=event_log,
        message=args.message,
    )
    print("Twilio smoke webhook server")
    print(f"- Listening: http://{args.host}:{args.port}")
    print(f"- Voice path: {VOICE_PATH}")
    print(f"- Status path: {STATUS_PATH}")
    print(f"- Event log: {event_log}")
    print("- Stop with Ctrl-C")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Twilio smoke webhook server")
    finally:
        server.server_close()
    return 0


def _build_server(
    *, host: str, port: int, event_log: Path, message: str
) -> ThreadingHTTPServer:
    class SmokeHandler(TwilioSmokeHandler):
        pass

    SmokeHandler.event_log = event_log
    SmokeHandler.message = message
    return ThreadingHTTPServer((host, port), SmokeHandler)


class TwilioSmokeHandler(BaseHTTPRequestHandler):
    event_log: Path
    message: str

    def do_GET(self) -> None:  # noqa: N802
        if self.path == HEALTH_PATH:
            self._send_json({"ok": True, "service": "twilio-smoke-webhook"})
            return
        self._send_plain("not found\n", status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        form = parse_form_body(
            content_type=self.headers.get("Content-Type", ""),
            content_length=self.headers.get("Content-Length"),
            body=self.rfile.read(_content_length(self.headers.get("Content-Length"))),
        )

        if self.path == VOICE_PATH:
            self._record_event("voice_incoming", form)
            self._send_twiml(build_voice_twiml(self.message))
            return

        if self.path == GATHER_PATH:
            self._record_event("gather_response", form)
            self._send_twiml(build_gather_response_twiml())
            return

        if self.path == STATUS_PATH:
            self._record_event("status_callback", form)
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return

        self._send_plain("not found\n", status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        sys.stdout.write(
            f"{self.log_date_time_string()} {self.address_string()} {format % args}\n"
        )

    def _record_event(self, event_type: str, form: dict[str, str]) -> None:
        event = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event_type,
            "path": self.path,
            "form": redact_form(form),
        }
        with self.event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        print(f"- Recorded {event_type}: {event['form']}")

    def _send_twiml(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_plain(self, body: str, *, status: HTTPStatus) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def parse_form_body(
    *, content_type: str, content_length: str | None, body: bytes
) -> dict[str, str]:
    if not content_length:
        return {}
    if "application/x-www-form-urlencoded" not in content_type:
        return {}
    parsed = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def build_voice_twiml(message: str) -> str:
    safe_message = escape(message)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Gather input="speech dtmf" timeout="5" action="{GATHER_PATH}" method="POST">'
        f"<Say>{safe_message}</Say>"
        "</Gather>"
        "<Say>Smoke test complete. Goodbye.</Say>"
        "<Hangup/>"
        "</Response>"
    )


def build_gather_response_twiml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Say>Thank you. The smoke test webhook recorded your response. Goodbye.</Say>"
        "<Hangup/>"
        "</Response>"
    )


def redact_form(form: dict[str, str]) -> dict[str, str]:
    return {key: redact_value(value) for key, value in form.items()}


def redact_value(value: str) -> str:
    stripped = value.strip()
    if SID_RE.fullmatch(stripped):
        return f"{stripped[:2]}...{stripped[-6:]}"
    if PHONE_RE.fullmatch(stripped):
        prefix = "+" if stripped.startswith("+") else ""
        return f"{prefix}...{stripped[-4:]}"
    return stripped


def _content_length(raw_value: str | None) -> int:
    if raw_value is None:
        return 0
    try:
        value = int(raw_value)
    except ValueError:
        return 0
    return max(0, min(value, 1_000_000))


if __name__ == "__main__":
    raise SystemExit(main())
