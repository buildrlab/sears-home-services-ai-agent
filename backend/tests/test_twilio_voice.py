from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect
from twilio.request_validator import RequestValidator

from app.config import Settings, get_settings
from app.dependencies import get_db_session
from app.main import create_app
from app.models import Appointment, AppointmentStatus, CallEvent, CallSession
from app.seed import seed_reference_data

BASE_URL = "https://api.test"
TWILIO_AUTH_TOKEN = "test-token"  # noqa: S105


def _client(
    db_session: Session,
    *,
    voice_mode: str = "gather",
    validate_requests: bool = True,
) -> TestClient:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        public_base_url=BASE_URL,
        twilio_auth_token=TWILIO_AUTH_TOKEN,
        twilio_validate_requests=validate_requests,
        twilio_voice_mode=voice_mode,
        twilio_conversation_relay_url="wss://ws.test/twilio/conversation",
    )
    app = create_app(settings)

    def override_session() -> Iterator[Session]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    def override_settings() -> Settings:
        return settings

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    return TestClient(app)


def _twilio_params(call_sid: str = "CA123456789") -> dict[str, str]:
    return {
        "CallSid": call_sid,
        "AccountSid": "AC123",
        "From": "+15551234567",
        "To": "+17373559397",
        "Caller": "+15551234567",
        "Called": "+17373559397",
    }


def _signed_headers(path: str, params: dict[str, str]) -> dict[str, str]:
    signature = RequestValidator(TWILIO_AUTH_TOKEN).compute_signature(
        f"{BASE_URL}{path}",
        params,
    )
    return {"X-Twilio-Signature": signature}


def _signed_websocket_headers() -> dict[str, str]:
    signature = RequestValidator(TWILIO_AUTH_TOKEN).compute_signature(
        "wss://ws.test/twilio/conversation",
        {},
    )
    return {"X-Twilio-Signature": signature}


def test_incoming_voice_accepts_signed_webhook_and_creates_call_session(
    db_session: Session,
) -> None:
    client = _client(db_session)
    params = _twilio_params()

    response = client.post(
        "/twilio/voice/incoming",
        data=params,
        headers=_signed_headers("/twilio/voice/incoming", params),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    assert "<Gather" in response.text
    call_session = db_session.scalars(select(CallSession)).one()
    assert call_session.call_sid == "CA123456789"
    assert call_session.from_number == "+15551234567"
    assert call_session.to_number == "+17373559397"
    assert call_session.diagnostic_session is not None
    event = db_session.scalars(select(CallEvent)).one()
    assert event.event_type == "voice_incoming"
    assert event.payload["From"] == "[redacted]"
    assert event.payload["To"] == "[redacted]"


def test_incoming_voice_rejects_missing_signature_when_validation_enabled(
    db_session: Session,
) -> None:
    client = _client(db_session)

    response = client.post("/twilio/voice/incoming", data=_twilio_params())

    assert response.status_code == 403
    assert db_session.scalars(select(CallSession)).all() == []


def test_incoming_voice_can_return_conversation_relay_twiml(db_session: Session) -> None:
    client = _client(db_session, voice_mode="conversationrelay")
    params = _twilio_params()

    response = client.post(
        "/twilio/voice/incoming",
        data=params,
        headers=_signed_headers("/twilio/voice/incoming", params),
    )

    assert response.status_code == 200
    assert "<ConversationRelay" in response.text
    assert 'url="wss://ws.test/twilio/conversation"' in response.text


def test_gather_response_runs_deterministic_diagnostic_turn(db_session: Session) -> None:
    client = _client(db_session)
    incoming_params = _twilio_params()
    client.post(
        "/twilio/voice/incoming",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/incoming", incoming_params),
    )
    gather_params = incoming_params | {"SpeechResult": "My refrigerator is not cooling in 75201."}

    response = client.post(
        "/twilio/voice/gather",
        data=gather_params,
        headers=_signed_headers("/twilio/voice/gather", gather_params),
    )

    assert response.status_code == 200
    assert "<Gather" in response.text
    assert "Safe checks:" in response.text
    assert "Do you prefer a morning or afternoon appointment" in response.text
    call_session = db_session.scalars(select(CallSession)).one()
    assert call_session.diagnostic_session is not None
    assert call_session.diagnostic_session.appliance_type == "refrigerator"
    assert call_session.diagnostic_session.zip_code == "75201"
    assert [event.event_type for event in call_session.events] == [
        "voice_incoming",
        "gather_response",
    ]


def test_gather_response_proposes_and_books_appointment_by_voice(db_session: Session) -> None:
    seed_reference_data(db_session)
    db_session.commit()
    client = _client(db_session)
    incoming_params = _twilio_params(call_sid="CAVOICEBOOK")
    client.post(
        "/twilio/voice/incoming",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/incoming", incoming_params),
    )
    diagnostic_params = incoming_params | {
        "SpeechResult": "My refrigerator is not cooling in 75201."
    }
    client.post(
        "/twilio/voice/gather",
        data=diagnostic_params,
        headers=_signed_headers("/twilio/voice/gather", diagnostic_params),
    )
    availability_params = incoming_params | {"SpeechResult": "Monday morning works."}

    proposal_response = client.post(
        "/twilio/voice/gather",
        data=availability_params,
        headers=_signed_headers("/twilio/voice/gather", availability_params),
    )

    assert proposal_response.status_code == 200
    assert "I found an appointment with Avery Johnson" in proposal_response.text
    assert "Say yes to book this appointment" in proposal_response.text
    appointment = db_session.scalars(select(Appointment)).one()
    assert appointment.status == AppointmentStatus.HELD.value

    confirmation_params = incoming_params | {"SpeechResult": "Yes, book it."}
    confirmation_response = client.post(
        "/twilio/voice/gather",
        data=confirmation_params,
        headers=_signed_headers("/twilio/voice/gather", confirmation_params),
    )

    assert confirmation_response.status_code == 200
    assert "appointment is confirmed" in confirmation_response.text
    db_session.refresh(appointment)
    assert appointment.status == AppointmentStatus.BOOKED.value
    assert appointment.confirmation_code is not None
    call_session = db_session.scalars(select(CallSession)).one()
    assert call_session.diagnostic_session is not None
    assert call_session.diagnostic_session.status == "scheduled"
    tool_names = [
        event.tool_name
        for event in call_session.diagnostic_session.events
        if event.tool_name is not None
    ]
    assert "propose_appointment" in tool_names
    assert "book_appointment" in tool_names


def test_status_callback_marks_call_completed(db_session: Session) -> None:
    client = _client(db_session)
    incoming_params = _twilio_params()
    client.post(
        "/twilio/voice/incoming",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/incoming", incoming_params),
    )
    status_params = incoming_params | {"CallStatus": "completed"}

    response = client.post(
        "/twilio/voice/status",
        data=status_params,
        headers=_signed_headers("/twilio/voice/status", status_params),
    )

    assert response.status_code == 204
    call_session = db_session.scalars(select(CallSession)).one()
    assert call_session.status == "completed"
    assert [event.event_type for event in call_session.events] == [
        "voice_incoming",
        "status_callback",
    ]


def test_conversation_relay_websocket_creates_session_and_returns_text(
    db_session: Session,
) -> None:
    client = _client(db_session)

    with client.websocket_connect(
        "/twilio/conversation",
        headers=_signed_websocket_headers(),
    ) as websocket:
        websocket.send_json({"type": "setup", "callSid": "CAWS123"})
        assert websocket.receive_json() == {"type": "setup_ack", "callSid": "CAWS123"}

        websocket.send_json(
            {"type": "prompt", "text": "My refrigerator is not cooling in 75201."}
        )
        response = websocket.receive_json()

    assert response["type"] == "text"
    assert response["last"] == "true"
    assert "Do you prefer a morning or afternoon appointment" in response["token"]
    call_session = db_session.scalars(select(CallSession)).one()
    assert call_session.call_sid == "CAWS123"
    assert [event.event_type for event in call_session.events] == [
        "conversation_setup",
        "conversation_prompt",
    ]


def test_conversation_relay_websocket_rejects_missing_signature(db_session: Session) -> None:
    client = _client(db_session)

    try:
        with client.websocket_connect("/twilio/conversation"):
            raise AssertionError("Unsigned ConversationRelay connection should be rejected.")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008
