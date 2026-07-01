"""Diagnostic agent providers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.agent.extraction import requests_image_upload
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
                    f"{', '.join(session.symptoms)}. "
                    f"{troubleshooting_guidance(session.appliance_type, session.symptoms)} "
                    "What ZIP code is the appliance in?"
                ),
                status=DiagnosticSessionStatus.ACTIVE,
            )

        if requests_image_upload(context.user_message):
            if not session.customer_email:
                return AgentTurnResult(
                    assistant_message=(
                        "What email address should I send the secure photo upload link to?"
                    ),
                    status=DiagnosticSessionStatus.ACTIVE,
                    recommended_action="collect_upload_email",
                )
            tool_call = validate_tool_call(
                ToolName.CREATE_UPLOAD_LINK.value,
                {"session_id": session.id, "email": session.customer_email},
            )
            return AgentTurnResult(
                assistant_message=(
                    "I can send a secure appliance photo upload link to "
                    f"{session.customer_email}."
                ),
                status=DiagnosticSessionStatus.ACTIVE,
                recommended_action="send_upload_link",
                tool_calls=[tool_call],
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
                f"{troubleshooting_guidance(session.appliance_type, session.symptoms)} "
                "If the issue continues, I can schedule a Sears Home Services technician. "
                "Do you prefer a morning or afternoon appointment?"
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
        fallback_result = DeterministicDiagnosticProvider().generate(context)
        response_tool_calls = list(_extract_tool_calls(getattr(response, "output", [])))
        tool_calls = response_tool_calls or fallback_result.tool_calls
        assistant_message = (getattr(response, "output_text", "") or "").strip()
        if not assistant_message:
            assistant_message = fallback_result.assistant_message

        has_scheduling_tool = any(
            call.name == ToolName.FIND_TECHNICIAN_MATCHES for call in tool_calls
        )
        should_use_fallback_state = not response_tool_calls
        return AgentTurnResult(
            assistant_message=assistant_message,
            status=(
                DiagnosticSessionStatus.READY_TO_SCHEDULE
                if has_scheduling_tool
                else fallback_result.status
                if should_use_fallback_state
                else DiagnosticSessionStatus.ACTIVE
            ),
            safety_blocked=fallback_result.safety_blocked if should_use_fallback_state else False,
            recommended_action=(
                "schedule_technician"
                if has_scheduling_tool
                else fallback_result.recommended_action
                if should_use_fallback_state
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
        "symptoms, ZIP code, and email when an image upload link is needed. Do not repeat "
        "questions for fields already known. Refuse "
        "unsafe troubleshooting involving gas, smoke, fire, sparking, electrical shock, or "
        "carbon monoxide, and steer to emergency help plus technician scheduling. Provide "
        "safe, basic troubleshooting steps before scheduling when the issue is not an "
        "emergency. Use tools only when their schemas are satisfied."
    )


def _input_messages(context: DiagnosticContext) -> list[dict[str, str]]:
    session = context.session
    state = (
        f"Known state: appliance={session.appliance_type or 'unknown'}; "
        f"symptoms={', '.join(session.symptoms or []) or 'unknown'}; "
        f"zip={session.zip_code or 'unknown'}; "
        f"email={session.customer_email or 'unknown'}; "
        f"safety_blocked={session.safety_blocked}."
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


def troubleshooting_guidance(appliance_type: str | None, symptoms: list[str] | None) -> str:
    appliance = (appliance_type or "appliance").lower()
    issue_set = set(symptoms or [])
    steps = _specific_troubleshooting_steps(appliance, issue_set)
    if not steps:
        steps = (
            "confirm the appliance has power",
            "check for obvious blocked vents, filters, or drains",
            "avoid disassembly or electrical work",
        )
    return "Safe checks: " + "; ".join(steps[:3]) + "."


def _specific_troubleshooting_steps(appliance: str, symptoms: set[str]) -> tuple[str, ...]:
    if appliance == "refrigerator":
        if {"not cooling", "leaking"} & symptoms:
            return (
                "make sure the doors seal fully",
                "confirm vents inside the refrigerator are not blocked",
                "move food away from the drain area and note where water appears",
            )
    if appliance == "washer":
        if {"not starting", "not draining", "leaking"} & symptoms:
            return (
                "confirm the lid or door is fully latched",
                "check that the water supply valves are open",
                "look for kinks in the drain hose without moving heavy equipment",
            )
    if appliance == "dryer":
        if {"not heating", "not starting", "making noise"} & symptoms:
            return (
                "clean the lint screen",
                "confirm the selected cycle uses heat",
                "stop using the dryer if there is burning smell or sparking",
            )
    if appliance == "dishwasher":
        if {"not draining", "leaking", "making noise"} & symptoms:
            return (
                "remove visible food debris from the filter area",
                "check that the door gasket is seated",
                "avoid reaching into moving parts",
            )
    if appliance == "oven":
        if {"not heating", "not starting"} & symptoms:
            return (
                "confirm the control is set to the correct mode",
                "check whether the display shows an error code",
                "stop using the oven if you smell gas or see sparking",
            )
    return ()
