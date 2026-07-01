"""Twilio voice request handling and call-session persistence."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request, WebSocket, WebSocketException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

from app.config import Settings
from app.models import CallEvent, CallSession, CallSessionStatus
from app.schemas import DiagnosticSessionCreate
from app.services.diagnostics import DiagnosticService


class TwilioVoiceService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def create_or_get_call_session(self, params: dict[str, str]) -> CallSession:
        call_sid = params.get("CallSid") or params.get("callSid")
        if not call_sid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="CallSid is required.",
            )

        statement = (
            select(CallSession)
            .where(CallSession.call_sid == call_sid)
            .options(selectinload(CallSession.events), selectinload(CallSession.diagnostic_session))
        )
        call_session = self._session.scalars(statement).one_or_none()
        if call_session is not None:
            return call_session

        diagnostic = DiagnosticService(self._session, self._settings).create_session(
            DiagnosticSessionCreate(
                external_call_id=call_sid,
                customer_phone=params.get("From") or params.get("Caller"),
            )
        )
        call_session = CallSession(
            call_sid=call_sid,
            diagnostic_session_id=diagnostic.id,
            from_number=params.get("From") or params.get("Caller"),
            to_number=params.get("To") or params.get("Called"),
            status=CallSessionStatus.ACTIVE.value,
            voice_mode=self._settings.twilio_voice_mode,
        )
        self._session.add(call_session)
        self._session.flush()
        return self.get_call_session(call_sid)

    def get_call_session(self, call_sid: str) -> CallSession:
        statement = (
            select(CallSession)
            .where(CallSession.call_sid == call_sid)
            .options(selectinload(CallSession.events), selectinload(CallSession.diagnostic_session))
        )
        call_session = self._session.scalars(statement).one_or_none()
        if call_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call session not found.",
            )
        return call_session

    def record_event(
        self,
        call_session: CallSession,
        *,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        self._session.add(
            CallEvent(
                call_session=call_session,
                event_type=event_type,
                payload=_redact_payload(payload),
            )
        )
        self._session.flush()

    def mark_status(self, call_session: CallSession, call_status: str | None) -> None:
        if call_status == "completed":
            call_session.status = CallSessionStatus.COMPLETED.value
        elif call_status in {"failed", "busy", "no-answer", "canceled"}:
            call_session.status = CallSessionStatus.FAILED.value
        self._session.flush()

    def process_speech(self, call_session: CallSession, speech: str) -> str:
        diagnostic_id = call_session.diagnostic_session_id
        if diagnostic_id is None:
            diagnostic = DiagnosticService(self._session, self._settings).create_session(
                DiagnosticSessionCreate(external_call_id=call_session.call_sid)
            )
            call_session.diagnostic_session_id = diagnostic.id
            self._session.flush()
            diagnostic_id = diagnostic.id
        result = DiagnosticService(self._session, self._settings).process_turn(
            session_id=diagnostic_id,
            message=speech,
        )
        return result.assistant_message


async def parse_twilio_form(request: Request) -> dict[str, str]:
    body = await request.body()
    return dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))


def validate_twilio_signature(
    request: Request,
    params: dict[str, str],
    settings: Settings,
) -> None:
    if not settings.twilio_validate_requests:
        return
    if not settings.twilio_auth_token:
        if settings.environment in {"local", "test"}:
            return
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio auth token is not configured.",
        )

    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing Twilio signature.",
        )

    url = _validation_url(request, settings)
    validator = RequestValidator(settings.twilio_auth_token)
    if not validator.validate(url, params, signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature.",
        )


def validate_twilio_websocket_signature(websocket: WebSocket, settings: Settings) -> None:
    if not settings.twilio_validate_requests:
        return
    if not settings.twilio_auth_token:
        if settings.environment in {"local", "test"}:
            return
        raise WebSocketException(code=status.WS_1011_INTERNAL_ERROR)

    signature = websocket.headers.get("X-Twilio-Signature")
    if not signature:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    url = _websocket_validation_url(websocket, settings)
    validator = RequestValidator(settings.twilio_auth_token)
    if not validator.validate(url, dict(websocket.query_params.multi_items()), signature):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)


def gather_twiml(*, prompt: str, action_url: str) -> str:
    response = VoiceResponse()
    gather = response.gather(
        input="speech",
        action=action_url,
        method="POST",
        speech_timeout="auto",
    )
    gather.say(prompt)
    response.say("I did not hear a response. Please call again when you are ready.")
    return str(response)


def conversation_relay_twiml(*, websocket_url: str) -> str:
    response = VoiceResponse()
    connect = response.connect()
    connect.conversation_relay(url=websocket_url)
    return str(response)


def websocket_text_response(text: str) -> dict[str, str]:
    return {"type": "text", "token": text, "last": "true"}


def websocket_setup_ack(call_sid: str) -> dict[str, str]:
    return {"type": "setup_ack", "callSid": call_sid}


def parse_websocket_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("WebSocket payload must be JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("WebSocket payload must be a JSON object.")
    return payload


def _validation_url(request: Request, settings: Settings) -> str:
    if settings.public_base_url:
        return f"{settings.public_base_url.rstrip('/')}{request.url.path}"
    return str(request.url)


def _websocket_validation_url(websocket: WebSocket, settings: Settings) -> str:
    url = settings.twilio_conversation_relay_url
    if websocket.url.query and "?" not in url:
        return f"{url}?{websocket.url.query}"
    return url


def _redact_payload(payload: dict[str, object]) -> dict[str, object]:
    redacted = dict(payload)
    for key in ("AccountSid", "From", "Caller", "To", "Called", "CallToken"):
        if key in redacted:
            redacted[key] = "[redacted]"
    return redacted
