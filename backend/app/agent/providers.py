"""Diagnostic agent providers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.agent.safety import SAFETY_RESPONSE
from app.agent.tools import AgentToolCall, ToolName, validate_tool_call
from app.config import Settings
from app.models import DiagnosticSession, DiagnosticSessionStatus


@dataclass(frozen=True)
class DiagnosticContext:
    session: DiagnosticSession
    user_message: str


@dataclass
class AgentTurnResult:
    assistant_message: str
    status: DiagnosticSessionStatus = DiagnosticSessionStatus.ACTIVE
    safety_blocked: bool = False
    recommended_action: str | None = None
    tool_calls: list[AgentToolCall] = field(default_factory=list)


class DiagnosticProvider(Protocol):
    def generate(self, context: DiagnosticContext) -> AgentTurnResult:
        """Generate the next agent turn."""


class DeterministicDiagnosticProvider:
    """Local deterministic workflow used for tests and no-key development."""

    def generate(self, context: DiagnosticContext) -> AgentTurnResult:
        session = context.session
        if session.safety_blocked:
            return AgentTurnResult(
                assistant_message=SAFETY_RESPONSE,
                status=DiagnosticSessionStatus.SAFETY_ESCALATED,
                safety_blocked=True,
                recommended_action="safety_escalation",
            )

        if not session.appliance_type:
            return AgentTurnResult(
                assistant_message="Which appliance needs help today?",
                status=DiagnosticSessionStatus.ACTIVE,
            )
        if not session.symptoms:
            return AgentTurnResult(
                assistant_message=f"What is happening with your {session.appliance_type}?",
                status=DiagnosticSessionStatus.ACTIVE,
            )
        if not session.zip_code:
            return AgentTurnResult(
                assistant_message=(
                    f"I have the {session.appliance_type} issue noted as "
                    f"{', '.join(session.symptoms)}. What ZIP code is the appliance in?"
                ),
                status=DiagnosticSessionStatus.ACTIVE,
            )

        tool_call = validate_tool_call(
            ToolName.FIND_TECHNICIAN_MATCHES.value,
            {
                "zip_code": session.zip_code,
                "appliance_type": session.appliance_type,
            },
        )
        return AgentTurnResult(
            assistant_message=(
                f"I have your {session.appliance_type} issue in ZIP {session.zip_code}. "
                "This needs technician scheduling, so I am checking available Sears Home "
                "Services technicians now."
            ),
            status=DiagnosticSessionStatus.READY_TO_SCHEDULE,
            recommended_action="schedule_technician",
            tool_calls=[tool_call],
        )


class OpenAIResponsesProvider:
    """OpenAI Responses API provider behind the diagnostic provider interface."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
        self._client = client
        self._settings = settings

    def generate(self, context: DiagnosticContext) -> AgentTurnResult:
        response = self._client.responses.create(
            model=self._settings.openai_model,
            instructions=_instructions(),
            input=_input_messages(context),
            tools=_openai_tools(),
            reasoning={"effort": self._settings.openai_reasoning_effort},
            text={"verbosity": self._settings.openai_verbosity},
        )
        tool_calls = list(_extract_tool_calls(getattr(response, "output", [])))
        assistant_message = getattr(response, "output_text", "") or (
            "I can help diagnose the issue and schedule service."
        )
        return AgentTurnResult(
            assistant_message=assistant_message,
            status=(
                DiagnosticSessionStatus.READY_TO_SCHEDULE
                if any(call.name == ToolName.FIND_TECHNICIAN_MATCHES for call in tool_calls)
                else DiagnosticSessionStatus.ACTIVE
            ),
            recommended_action=(
                "schedule_technician"
                if any(call.name == ToolName.FIND_TECHNICIAN_MATCHES for call in tool_calls)
                else None
            ),
            tool_calls=tool_calls,
        )


def build_diagnostic_provider(settings: Settings) -> DiagnosticProvider:
    if settings.openai_api_key:
        return OpenAIResponsesProvider(settings)
    return DeterministicDiagnosticProvider()


def _instructions() -> str:
    return (
        "You are a Sears Home Services appliance diagnostic agent. Collect appliance type, "
        "symptoms, and ZIP code. Do not repeat questions for fields already known. Refuse "
        "unsafe troubleshooting involving gas, smoke, fire, sparking, electrical shock, or "
        "carbon monoxide, and steer to emergency help plus technician scheduling. Use tools "
        "only when their schemas are satisfied."
    )


def _input_messages(context: DiagnosticContext) -> list[dict[str, str]]:
    session = context.session
    state = (
        f"Known state: appliance={session.appliance_type or 'unknown'}; "
        f"symptoms={', '.join(session.symptoms or []) or 'unknown'}; "
        f"zip={session.zip_code or 'unknown'}; safety_blocked={session.safety_blocked}."
    )
    return [
        {"role": "system", "content": state},
        {"role": "user", "content": context.user_message},
    ]


def _openai_tools() -> list[dict[str, Any]]:
    from app.agent.tools import OPENAI_TOOL_DEFINITIONS

    return OPENAI_TOOL_DEFINITIONS


def _extract_tool_calls(output_items: Iterable[Any]) -> Iterable[AgentToolCall]:
    for item in output_items:
        item_type = _read_attr(item, "type")
        if item_type != "function_call":
            continue
        yield validate_tool_call(
            str(_read_attr(item, "name")),
            _read_attr(item, "arguments") or {},
        )


def _read_attr(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)
