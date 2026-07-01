"""Twilio voice request handling and call-session persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request, WebSocket, WebSocketException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

from app.config import Settings
from app.exceptions import InvalidSchedulingRequestError, SlotUnavailableError
from app.models import (
    Appointment,
    CallEvent,
    CallSession,
    CallSessionStatus,
    DiagnosticEvent,
    DiagnosticEventRole,
    DiagnosticSession,
    DiagnosticSessionStatus,
)
from app.schemas import CustomerCreate, DiagnosticSessionCreate
from app.services.diagnostics import DiagnosticService
from app.services.scheduling import SchedulingService

CONFIRMATION_TERMS = ("yes", "book", "confirm", "schedule it", "that works")
AVAILABILITY_TERMS = (
    "morning",
    "afternoon",
    "am",
    "pm",
    "any time",
    "anytime",
    "soonest",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
MAX_EMPTY_SPEECH_RETRIES = 2


@dataclass(frozen=True)
class VoicePrompt:
    prompt: str
    continue_gather: bool = True


class TwilioVoiceService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def create_or_get_call_session(self, params: dict[str, str]) -> CallSession:
        call_sid = params.get("CallSid") or params.get("callSid")
        if not call_sid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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

        diagnostic_session = call_session.diagnostic_session
        if diagnostic_session is None:
            diagnostic_session = DiagnosticService(self._session, self._settings).get_session(
                diagnostic_id
            )

        if _is_booking_confirmation(speech):
            booked_message = self._book_latest_proposal(diagnostic_session, speech)
            if booked_message is not None:
                return booked_message

        result = DiagnosticService(self._session, self._settings).process_turn(
            session_id=diagnostic_id,
            message=speech,
        )
        diagnostic_session = DiagnosticService(self._session, self._settings).get_session(
            diagnostic_id
        )
        if (
            diagnostic_session.status == DiagnosticSessionStatus.READY_TO_SCHEDULE.value
            and _has_availability_preference(speech)
        ):
            proposal = self._create_voice_appointment_proposal(diagnostic_session, speech)
            if proposal is not None:
                return proposal
        return result.assistant_message

    def process_empty_speech(self, call_session: CallSession) -> VoicePrompt:
        empty_attempts = self._empty_speech_attempts(call_session)
        if empty_attempts > MAX_EMPTY_SPEECH_RETRIES:
            return VoicePrompt(
                prompt=(
                    "I still could not hear a response. Please call back when you are ready, "
                    "or contact Sears Home Services online to schedule service."
                ),
                continue_gather=False,
            )

        diagnostic_session = call_session.diagnostic_session
        if diagnostic_session is None and call_session.diagnostic_session_id is not None:
            diagnostic_session = DiagnosticService(self._session, self._settings).get_session(
                call_session.diagnostic_session_id
            )

        return VoicePrompt(prompt=_empty_retry_prompt(diagnostic_session))

    def _book_latest_proposal(
        self,
        diagnostic_session: DiagnosticSession,
        speech: str,
    ) -> str | None:
        appointment_id = _latest_proposed_appointment_id(diagnostic_session)
        if appointment_id is None:
            return None

        self._add_diagnostic_event(
            diagnostic_session,
            role=DiagnosticEventRole.USER,
            content=speech,
        )
        appointment = SchedulingService(self._session).book_appointment(appointment_id)
        diagnostic_session.status = DiagnosticSessionStatus.SCHEDULED.value
        diagnostic_session.recommended_action = "appointment_confirmed"
        self._add_diagnostic_event(
            diagnostic_session,
            role=DiagnosticEventRole.TOOL,
            content="Booked technician appointment.",
            tool_name="book_appointment",
            tool_payload=_appointment_payload(appointment),
        )
        message = _booking_confirmation_message(appointment)
        self._add_diagnostic_event(
            diagnostic_session,
            role=DiagnosticEventRole.ASSISTANT,
            content=message,
        )
        self._session.flush()
        return message

    def _create_voice_appointment_proposal(
        self,
        diagnostic_session: DiagnosticSession,
        speech: str,
    ) -> str | None:
        if not diagnostic_session.appliance_type or not diagnostic_session.zip_code:
            return None

        service = SchedulingService(self._session)
        try:
            appointment = service.create_first_available_hold(
                zip_code=diagnostic_session.zip_code,
                appliance_type=diagnostic_session.appliance_type,
                customer=_customer_from_diagnostic_session(diagnostic_session),
                issue_summary=_issue_summary(diagnostic_session),
                availability_preference=speech,
            )
        except (InvalidSchedulingRequestError, SlotUnavailableError):
            message = (
                "I could not find an available matching slot for that preference. "
                "Would a different morning or afternoon work?"
            )
            self._add_diagnostic_event(
                diagnostic_session,
                role=DiagnosticEventRole.ASSISTANT,
                content=message,
            )
            self._session.flush()
            return message

        self._add_diagnostic_event(
            diagnostic_session,
            role=DiagnosticEventRole.TOOL,
            content="Proposed technician appointment.",
            tool_name="propose_appointment",
            tool_payload=_appointment_payload(appointment),
        )
        message = _appointment_proposal_message(appointment)
        self._add_diagnostic_event(
            diagnostic_session,
            role=DiagnosticEventRole.ASSISTANT,
            content=message,
        )
        self._session.flush()
        return message

    def _add_diagnostic_event(
        self,
        diagnostic_session: DiagnosticSession,
        *,
        role: DiagnosticEventRole,
        content: str,
        tool_name: str | None = None,
        tool_payload: dict[str, object] | None = None,
    ) -> None:
        self._session.add(
            DiagnosticEvent(
                session=diagnostic_session,
                role=role.value,
                content=content,
                tool_name=tool_name,
                tool_payload=tool_payload,
            )
        )

    def _empty_speech_attempts(self, call_session: CallSession) -> int:
        statement = (
            select(CallEvent)
            .where(CallEvent.call_session_id == call_session.id)
            .where(CallEvent.event_type == "gather_response")
            .order_by(CallEvent.id)
        )
        attempts = 0
        for event in self._session.scalars(statement):
            speech_result = event.payload.get("SpeechResult")
            if not isinstance(speech_result, str) or not speech_result.strip():
                attempts += 1
        return attempts


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
        action_on_empty_result=True,
        speech_timeout="auto",
    )
    gather.say(prompt)
    response.redirect(action_url, method="POST")
    return str(response)


def say_and_hangup_twiml(*, prompt: str) -> str:
    response = VoiceResponse()
    response.say(prompt)
    response.hangup()
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


def _is_booking_confirmation(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in CONFIRMATION_TERMS)


def _has_availability_preference(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in AVAILABILITY_TERMS)


def _empty_retry_prompt(diagnostic_session: DiagnosticSession | None) -> str:
    if diagnostic_session is None or not diagnostic_session.appliance_type:
        return (
            "I did not catch that. Please say the appliance and what is happening, "
            "for example, my refrigerator is not cooling."
        )
    if not diagnostic_session.symptoms:
        return (
            f"I heard {diagnostic_session.appliance_type}. What is happening with it? "
            "For example, say it is leaking or not cooling."
        )
    if not diagnostic_session.zip_code:
        return (
            f"I have the {diagnostic_session.appliance_type} issue noted as "
            f"{', '.join(diagnostic_session.symptoms)}. Please say the five digit ZIP code."
        )
    if diagnostic_session.status == DiagnosticSessionStatus.READY_TO_SCHEDULE.value:
        return (
            "I have enough detail to schedule service. Please say morning or afternoon, "
            "or say a weekday like Monday morning."
        )
    return "I did not catch that. Please say that again in a short phrase."


def _latest_proposed_appointment_id(diagnostic_session: DiagnosticSession) -> int | None:
    for event in reversed(diagnostic_session.events):
        if event.tool_name != "propose_appointment" or not event.tool_payload:
            continue
        appointment_id = event.tool_payload.get("appointment_id")
        if isinstance(appointment_id, int):
            return appointment_id
    return None


def _customer_from_diagnostic_session(diagnostic_session: DiagnosticSession) -> CustomerCreate:
    return CustomerCreate(
        full_name=diagnostic_session.customer_name or "Voice Caller",
        email=diagnostic_session.customer_email,
        phone=diagnostic_session.customer_phone or "+15550000000",
    )


def _issue_summary(diagnostic_session: DiagnosticSession) -> str:
    symptom_text = ", ".join(diagnostic_session.symptoms or []) or "reported issue"
    appliance = diagnostic_session.appliance_type or "appliance"
    return f"Voice diagnostic for {appliance}: {symptom_text}."


def _appointment_payload(appointment: Appointment) -> dict[str, object]:
    return {
        "appointment_id": appointment.id,
        "status": appointment.status,
        "technician": appointment.technician.name,
        "scheduled_start": appointment.scheduled_start.isoformat(),
        "scheduled_end": appointment.scheduled_end.isoformat(),
        "confirmation_code": appointment.confirmation_code,
    }


def _appointment_proposal_message(appointment: Appointment) -> str:
    return (
        "I found an appointment with "
        f"{appointment.technician.name} on {_format_voice_datetime(appointment.scheduled_start)}. "
        "Say yes to book this appointment, or tell me another morning or afternoon."
    )


def _booking_confirmation_message(appointment: Appointment) -> str:
    return (
        "Your Sears Home Services appointment is confirmed with "
        f"{appointment.technician.name} on {_format_voice_datetime(appointment.scheduled_start)}. "
        f"Your confirmation code is {appointment.confirmation_code}. "
        "Please keep the area around the appliance accessible for the technician."
    )


def _format_voice_datetime(value: datetime) -> str:
    return value.strftime("%A at %-I:%M %p")
