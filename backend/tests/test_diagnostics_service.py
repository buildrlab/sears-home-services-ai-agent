from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import DiagnosticEventRole, DiagnosticSessionStatus
from app.schemas import DiagnosticSessionCreate
from app.services.diagnostics import DiagnosticService


def _service(db_session: Session) -> DiagnosticService:
    return DiagnosticService(db_session, Settings(environment="test"))


def test_diagnostic_workflow_remembers_appliance_and_symptoms(db_session: Session) -> None:
    service = _service(db_session)
    session = service.create_session(DiagnosticSessionCreate(customer_phone="+15551234567"))

    result = service.process_turn(
        session_id=session.id,
        message="My refrigerator is not cooling and leaking.",
    )
    persisted = service.get_session(session.id)

    assert persisted.appliance_type == "refrigerator"
    assert persisted.symptoms == ["not cooling", "leaking"]
    assert "Safe checks:" in result.assistant_message
    assert "What ZIP code" in result.assistant_message
    assert "Which appliance" not in result.assistant_message


def test_diagnostic_workflow_does_not_reask_known_fields(db_session: Session) -> None:
    service = _service(db_session)
    session = service.create_session(DiagnosticSessionCreate())
    service.process_turn(session_id=session.id, message="My dryer is not heating.")

    result = service.process_turn(session_id=session.id, message="The ZIP code is 76102.")

    assert "What is happening" not in result.assistant_message
    assert result.tool_calls[0].name == "find_technician_matches"
    assert result.tool_calls[0].arguments == {"zip_code": "76102", "appliance_type": "dryer"}


def test_diagnostic_workflow_escalates_to_scheduling_when_unresolved(
    db_session: Session,
) -> None:
    service = _service(db_session)
    session = service.create_session(DiagnosticSessionCreate())

    result = service.process_turn(
        session_id=session.id,
        message="My washer will not start in 78205.",
    )
    persisted = service.get_session(session.id)

    assert persisted.status == DiagnosticSessionStatus.READY_TO_SCHEDULE.value
    assert persisted.recommended_action == "schedule_technician"
    assert "Do you prefer a morning or afternoon appointment" in result.assistant_message
    assert result.tool_calls[0].name == "find_technician_matches"


def test_diagnostic_workflow_captures_email_and_requests_upload_link(
    db_session: Session,
) -> None:
    service = _service(db_session)
    session = service.create_session(DiagnosticSessionCreate())
    service.process_turn(
        session_id=session.id,
        message="My refrigerator is leaking in 75201.",
    )

    result = service.process_turn(
        session_id=session.id,
        message="Please send a photo upload link to Customer@Example.Test.",
    )
    persisted = service.get_session(session.id)

    assert persisted.customer_email == "customer@example.test"
    assert result.recommended_action == "send_upload_link"
    assert result.tool_calls[0].name == "create_upload_link"
    assert result.tool_calls[0].arguments == {
        "session_id": session.id,
        "email": "customer@example.test",
    }


def test_diagnostic_workflow_uses_email_after_prior_upload_request(
    db_session: Session,
) -> None:
    service = _service(db_session)
    session = service.create_session(DiagnosticSessionCreate())
    service.process_turn(
        session_id=session.id,
        message="My refrigerator is leaking in 75201 and I can send a photo.",
    )

    result = service.process_turn(
        session_id=session.id,
        message="Customer@Example.Test",
    )
    persisted = service.get_session(session.id)

    assert persisted.customer_email == "customer@example.test"
    assert result.recommended_action == "send_upload_link"
    assert result.tool_calls[0].name == "create_upload_link"
    assert result.tool_calls[0].arguments == {
        "session_id": session.id,
        "email": "customer@example.test",
    }


def test_diagnostic_workflow_refuses_unsafe_troubleshooting(db_session: Session) -> None:
    service = _service(db_session)
    session = service.create_session(DiagnosticSessionCreate())

    result = service.process_turn(
        session_id=session.id,
        message="The oven has a gas smell and I want to fix the gas line.",
    )
    persisted = service.get_session(session.id)

    assert persisted.status == DiagnosticSessionStatus.SAFETY_ESCALATED.value
    assert persisted.safety_blocked is True
    assert "stop using the appliance" in result.assistant_message
    assert "fix the gas line" not in result.assistant_message


def test_diagnostic_events_are_persisted_in_order(db_session: Session) -> None:
    service = _service(db_session)
    session = service.create_session(DiagnosticSessionCreate())

    service.process_turn(session_id=session.id, message="My fridge is warm in 75201.")
    persisted = service.get_session(session.id)

    assert [event.role for event in persisted.events] == [
        DiagnosticEventRole.SYSTEM.value,
        DiagnosticEventRole.USER.value,
        DiagnosticEventRole.ASSISTANT.value,
        DiagnosticEventRole.TOOL.value,
    ]
