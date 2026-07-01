"""Diagnostic conversation service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.extraction import (
    extract_appliance_type,
    extract_email,
    extract_symptoms,
    extract_zip_code,
)
from app.agent.providers import (
    AgentTurnResult,
    DiagnosticContext,
    DiagnosticProvider,
    build_diagnostic_provider,
)
from app.agent.safety import is_unsafe_troubleshooting_request
from app.config import Settings
from app.exceptions import DiagnosticSessionNotFoundError
from app.models import (
    DiagnosticEvent,
    DiagnosticEventRole,
    DiagnosticSession,
    DiagnosticSessionStatus,
)
from app.schemas import DiagnosticSessionCreate


class DiagnosticService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        provider: DiagnosticProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._provider = provider or build_diagnostic_provider(settings)

    def create_session(self, request: DiagnosticSessionCreate) -> DiagnosticSession:
        diagnostic_session = DiagnosticSession(
            external_call_id=request.external_call_id,
            customer_name=request.customer_name,
            customer_email=_normalize_optional(request.customer_email, lower=True),
            customer_phone=_normalize_optional(request.customer_phone),
            symptoms=[],
            status=DiagnosticSessionStatus.ACTIVE.value,
            safety_blocked=False,
        )
        self._session.add(diagnostic_session)
        self._session.flush()
        self._add_event(
            diagnostic_session,
            role=DiagnosticEventRole.SYSTEM,
            content="Diagnostic session created.",
        )
        self._session.flush()
        return self.get_session(diagnostic_session.id)

    def get_session(self, session_id: int) -> DiagnosticSession:
        statement = (
            select(DiagnosticSession)
            .where(DiagnosticSession.id == session_id)
            .options(selectinload(DiagnosticSession.events))
        )
        diagnostic_session = self._session.scalars(statement).one_or_none()
        if diagnostic_session is None:
            raise DiagnosticSessionNotFoundError("Diagnostic session not found.")
        return diagnostic_session

    def list_sessions(self) -> list[DiagnosticSession]:
        statement = (
            select(DiagnosticSession)
            .options(selectinload(DiagnosticSession.events))
            .order_by(DiagnosticSession.id.desc())
        )
        return list(self._session.scalars(statement).all())

    def process_turn(self, *, session_id: int, message: str) -> AgentTurnResult:
        diagnostic_session = self.get_session(session_id)
        self._add_event(diagnostic_session, role=DiagnosticEventRole.USER, content=message)
        self._apply_message_state(diagnostic_session, message)

        result = self._provider.generate(
            DiagnosticContext(session=diagnostic_session, user_message=message)
        )
        self._apply_provider_result(diagnostic_session, result)
        self._add_event(
            diagnostic_session,
            role=DiagnosticEventRole.ASSISTANT,
            content=result.assistant_message,
        )
        for tool_call in result.tool_calls:
            self._add_event(
                diagnostic_session,
                role=DiagnosticEventRole.TOOL,
                content=f"Requested tool: {tool_call.name.value}",
                tool_name=tool_call.name.value,
                tool_payload=tool_call.arguments,
            )
        self._session.flush()
        return result

    def _apply_message_state(self, diagnostic_session: DiagnosticSession, message: str) -> None:
        if is_unsafe_troubleshooting_request(message):
            diagnostic_session.safety_blocked = True
            diagnostic_session.status = DiagnosticSessionStatus.SAFETY_ESCALATED.value
            diagnostic_session.recommended_action = "safety_escalation"
            return

        if diagnostic_session.appliance_type is None:
            diagnostic_session.appliance_type = extract_appliance_type(message)

        diagnostic_session.symptoms = extract_symptoms(message, diagnostic_session.symptoms)

        if diagnostic_session.zip_code is None:
            diagnostic_session.zip_code = extract_zip_code(message)

        if diagnostic_session.customer_email is None:
            diagnostic_session.customer_email = extract_email(message)

    def _apply_provider_result(
        self,
        diagnostic_session: DiagnosticSession,
        result: AgentTurnResult,
    ) -> None:
        diagnostic_session.status = result.status.value
        diagnostic_session.safety_blocked = (
            result.safety_blocked or diagnostic_session.safety_blocked
        )
        diagnostic_session.recommended_action = result.recommended_action

    def _add_event(
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


def _normalize_optional(value: str | None, *, lower: bool = False) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if lower:
        return stripped.lower()
    return stripped
