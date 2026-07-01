from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import HTTPException
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
from app.services.twilio_voice import TwilioVoiceService, parse_websocket_payload

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
    assert "actionOnEmptyResult" in response.text
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


def test_incoming_voice_rejects_invalid_signature_when_validation_enabled(
    db_session: Session,
) -> None:
    client = _client(db_session)

    response = client.post(
        "/twilio/voice/incoming",
        data=_twilio_params(),
        headers={"X-Twilio-Signature": "invalid"},
    )

    assert response.status_code == 403
    assert db_session.scalars(select(CallSession)).all() == []


def test_incoming_voice_allows_unsigned_webhook_when_validation_disabled(
    db_session: Session,
) -> None:
    client = _client(db_session, validate_requests=False)

    response = client.post("/twilio/voice/incoming", data=_twilio_params(call_sid="CAUNSIGNED"))

    assert response.status_code == 200
    call_session = db_session.scalars(select(CallSession)).one()
    assert call_session.call_sid == "CAUNSIGNED"


def test_incoming_voice_requires_call_sid(db_session: Session) -> None:
    client = _client(db_session)
    params = _twilio_params()
    params.pop("CallSid")

    response = client.post(
        "/twilio/voice/incoming",
        data=params,
        headers=_signed_headers("/twilio/voice/incoming", params),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "CallSid is required."


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


def test_gather_response_split_turn_collects_zip_without_reasking_known_fields(
    db_session: Session,
) -> None:
    client = _client(db_session)
    incoming_params = _twilio_params(call_sid="CASPLITTURN")
    client.post(
        "/twilio/voice/incoming",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/incoming", incoming_params),
    )

    first_params = incoming_params | {
        "SpeechResult": "My refrigerator is not cooling and leaking."
    }
    first_response = client.post(
        "/twilio/voice/gather",
        data=first_params,
        headers=_signed_headers("/twilio/voice/gather", first_params),
    )

    assert first_response.status_code == 200
    assert "What ZIP code is the appliance in" in first_response.text
    assert "Which appliance needs help" not in first_response.text
    assert "What is happening with your refrigerator" not in first_response.text

    second_params = incoming_params | {"SpeechResult": "The ZIP code is 75201."}
    second_response = client.post(
        "/twilio/voice/gather",
        data=second_params,
        headers=_signed_headers("/twilio/voice/gather", second_params),
    )

    assert second_response.status_code == 200
    assert "Safe checks:" in second_response.text
    assert "Do you prefer a morning or afternoon appointment" in second_response.text
    assert "Which appliance needs help" not in second_response.text
    assert "What is happening with your refrigerator" not in second_response.text
    call_session = db_session.scalars(select(CallSession)).one()
    assert call_session.diagnostic_session is not None
    assert call_session.diagnostic_session.appliance_type == "refrigerator"
    assert call_session.diagnostic_session.symptoms == ["not cooling", "leaking"]
    assert call_session.diagnostic_session.zip_code == "75201"
    assert call_session.diagnostic_session.status == "ready_to_schedule"


def test_gather_response_retries_blank_speech_before_hanging_up(db_session: Session) -> None:
    client = _client(db_session)
    incoming_params = _twilio_params(call_sid="CABLANK")
    client.post(
        "/twilio/voice/incoming",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/incoming", incoming_params),
    )

    first_response = client.post(
        "/twilio/voice/gather",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/gather", incoming_params),
    )

    assert first_response.status_code == 200
    assert "<Gather" in first_response.text
    assert "I did not catch that" in first_response.text
    assert "Please say the appliance and what is happening" in first_response.text

    second_response = client.post(
        "/twilio/voice/gather",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/gather", incoming_params),
    )

    assert second_response.status_code == 200
    assert "<Gather" in second_response.text
    assert "I did not catch that" in second_response.text

    final_response = client.post(
        "/twilio/voice/gather",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/gather", incoming_params),
    )

    assert final_response.status_code == 200
    assert "<Gather" not in final_response.text
    assert "<Hangup" in final_response.text
    assert "I still could not hear a response" in final_response.text


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


def test_gather_response_prompts_for_alternate_availability_when_no_slot_matches(
    db_session: Session,
) -> None:
    client = _client(db_session)
    incoming_params = _twilio_params(call_sid="CANOSLOT")
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

    response = client.post(
        "/twilio/voice/gather",
        data=availability_params,
        headers=_signed_headers("/twilio/voice/gather", availability_params),
    )

    assert response.status_code == 200
    assert "I could not find an available matching slot" in response.text
    assert "Would a different morning or afternoon work" in response.text
    assert db_session.scalars(select(Appointment)).all() == []


def test_gather_response_alternate_availability_keeps_existing_proposal_held(
    db_session: Session,
) -> None:
    seed_reference_data(db_session)
    db_session.commit()
    client = _client(db_session)
    incoming_params = _twilio_params(call_sid="CAALTERNATE")
    client.post(
        "/twilio/voice/incoming",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/incoming", incoming_params),
    )
    client.post(
        "/twilio/voice/gather",
        data=incoming_params | {"SpeechResult": "My refrigerator is not cooling in 75201."},
        headers=_signed_headers(
            "/twilio/voice/gather",
            incoming_params | {"SpeechResult": "My refrigerator is not cooling in 75201."},
        ),
    )
    client.post(
        "/twilio/voice/gather",
        data=incoming_params | {"SpeechResult": "Monday morning works."},
        headers=_signed_headers(
            "/twilio/voice/gather",
            incoming_params | {"SpeechResult": "Monday morning works."},
        ),
    )

    response = client.post(
        "/twilio/voice/gather",
        data=incoming_params | {"SpeechResult": "No, another afternoon."},
        headers=_signed_headers(
            "/twilio/voice/gather",
            incoming_params | {"SpeechResult": "No, another afternoon."},
        ),
    )

    assert response.status_code == 200
    appointments = db_session.scalars(select(Appointment)).all()
    assert appointments
    assert {appointment.status for appointment in appointments} == {AppointmentStatus.HELD.value}
    call_session = db_session.scalars(select(CallSession)).one()
    assert call_session.diagnostic_session is not None
    tool_names = [
        event.tool_name
        for event in call_session.diagnostic_session.events
        if event.tool_name is not None
    ]
    assert tool_names.count("propose_appointment") >= 1
    assert "book_appointment" not in tool_names


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


def test_status_callback_marks_failed_call_statuses(db_session: Session) -> None:
    client = _client(db_session)
    incoming_params = _twilio_params(call_sid="CAFAILED")
    client.post(
        "/twilio/voice/incoming",
        data=incoming_params,
        headers=_signed_headers("/twilio/voice/incoming", incoming_params),
    )
    status_params = incoming_params | {"CallStatus": "failed"}

    response = client.post(
        "/twilio/voice/status",
        data=status_params,
        headers=_signed_headers("/twilio/voice/status", status_params),
    )

    assert response.status_code == 204
    call_session = db_session.scalars(select(CallSession)).one()
    assert call_session.status == "failed"


def test_twilio_service_returns_existing_call_session_and_404_for_missing(
    db_session: Session,
) -> None:
    service = TwilioVoiceService(db_session, Settings(environment="test"))
    created = service.create_or_get_call_session({"CallSid": "CAEXISTING"})

    assert service.create_or_get_call_session({"CallSid": "CAEXISTING"}).id == created.id
    with pytest.raises(HTTPException) as exc:
        service.get_call_session("CAMISSING")
    assert exc.value.status_code == 404


def test_twilio_service_process_speech_recovers_detached_call_session(
    db_session: Session,
) -> None:
    service = TwilioVoiceService(db_session, Settings(environment="test"))
    call_session = CallSession(call_sid="CADETACHED", status="active", voice_mode="gather")
    db_session.add(call_session)
    db_session.flush()

    response = service.process_speech(call_session, "My washer will not start in 78205.")

    assert call_session.diagnostic_session_id is not None
    assert "Do you prefer a morning or afternoon appointment" in response


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


def test_conversation_relay_websocket_handles_invalid_blank_and_unknown_events(
    db_session: Session,
) -> None:
    client = _client(db_session)

    with client.websocket_connect(
        "/twilio/conversation",
        headers=_signed_websocket_headers(),
    ) as websocket:
        websocket.send_text("not-json")
        assert websocket.receive_json() == {
            "type": "error",
            "message": "Invalid JSON payload.",
        }

        websocket.send_json({"type": "setup", "callSid": "CAWSERR"})
        assert websocket.receive_json() == {"type": "setup_ack", "callSid": "CAWSERR"}

        websocket.send_json({"type": "text", "text": ""})
        repeat_response = websocket.receive_json()
        response_text = repeat_response.get("token")
        assert "I did not catch that" in response_text
        assert "Please say the appliance and what is happening" in response_text

        websocket.send_json({"type": "unsupported"})
        assert websocket.receive_json() == {
            "type": "error",
            "message": "Unsupported event.",
        }


def test_parse_websocket_payload_rejects_non_object_json() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        parse_websocket_payload('["not", "an", "object"]')


def test_conversation_relay_websocket_rejects_missing_signature(db_session: Session) -> None:
    client = _client(db_session)

    try:
        with client.websocket_connect("/twilio/conversation"):
            raise AssertionError("Unsigned ConversationRelay connection should be rejected.")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008
