from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.agent.providers import (
    DeterministicDiagnosticProvider,
    DiagnosticContext,
    OpenAIResponsesProvider,
    build_diagnostic_provider,
    troubleshooting_guidance,
)
from app.config import Settings
from app.models import DiagnosticSession, DiagnosticSessionStatus


class FakeResponses:
    def __init__(
        self,
        *,
        output_text: str = "I will check technician availability.",
        output: list[Any] | None = None,
    ) -> None:
        self.kwargs = {}
        self.output_text = output_text
        self.output = output or [
            {
                "type": "function_call",
                "name": "find_technician_matches",
                "arguments": '{"zip_code":"75201","appliance_type":"refrigerator"}',
            }
        ]

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.output_text, output=self.output)


class FakeClient:
    def __init__(
        self,
        *,
        output_text: str = "I will check technician availability.",
        output: list[Any] | None = None,
    ) -> None:
        self.responses = FakeResponses(output_text=output_text, output=output)


def _session(**overrides) -> DiagnosticSession:
    defaults = {
        "id": 1,
        "appliance_type": "refrigerator",
        "symptoms": ["not cooling"],
        "zip_code": "75201",
        "safety_blocked": False,
    }
    defaults.update(overrides)
    return DiagnosticSession(**defaults)


def test_deterministic_provider_prompts_for_missing_appliance_type() -> None:
    provider = DeterministicDiagnosticProvider()

    result = provider.generate(
        DiagnosticContext(
            session=_session(appliance_type=None, symptoms=[], zip_code=None),
            user_message="I need help.",
        )
    )

    assert result.status == DiagnosticSessionStatus.ACTIVE
    assert result.assistant_message == "Which appliance needs help today?"
    assert result.tool_calls == []


def test_deterministic_provider_prompts_for_missing_symptoms() -> None:
    provider = DeterministicDiagnosticProvider()

    result = provider.generate(
        DiagnosticContext(
            session=_session(appliance_type="washer", symptoms=[], zip_code=None),
            user_message="It is my washer.",
        )
    )

    assert result.status == DiagnosticSessionStatus.ACTIVE
    assert result.assistant_message == "What is happening with your washer?"


def test_deterministic_provider_prompts_for_zip_after_guidance() -> None:
    provider = DeterministicDiagnosticProvider()

    result = provider.generate(
        DiagnosticContext(
            session=_session(appliance_type="dryer", symptoms=["not heating"], zip_code=None),
            user_message="It is not heating.",
        )
    )

    assert result.status == DiagnosticSessionStatus.ACTIVE
    assert "Safe checks: clean the lint screen" in result.assistant_message
    assert "What ZIP code is the appliance in?" in result.assistant_message


def test_deterministic_provider_blocks_safety_escalated_session() -> None:
    provider = DeterministicDiagnosticProvider()

    result = provider.generate(
        DiagnosticContext(
            session=_session(safety_blocked=True),
            user_message="Can I keep working on the gas line?",
        )
    )

    assert result.status == DiagnosticSessionStatus.SAFETY_ESCALATED
    assert result.safety_blocked is True
    assert result.recommended_action == "safety_escalation"
    assert "stop using the appliance" in result.assistant_message


def test_deterministic_provider_collects_email_before_upload_link() -> None:
    provider = DeterministicDiagnosticProvider()

    result = provider.generate(
        DiagnosticContext(
            session=_session(customer_email=None),
            user_message="Can I upload a photo?",
        )
    )

    assert result.status == DiagnosticSessionStatus.ACTIVE
    assert result.recommended_action == "collect_upload_email"
    assert result.tool_calls == []
    assert "What email address" in result.assistant_message


def test_deterministic_provider_creates_upload_link_tool_call() -> None:
    provider = DeterministicDiagnosticProvider()

    result = provider.generate(
        DiagnosticContext(
            session=_session(id=42, customer_email="customer@example.test"),
            user_message="Can I upload a picture?",
        )
    )

    assert result.recommended_action == "send_upload_link"
    assert result.tool_calls[0].name == "create_upload_link"
    assert result.tool_calls[0].arguments == {
        "session_id": 42,
        "email": "customer@example.test",
    }


def test_deterministic_provider_recommends_scheduling_with_matching_tool_call() -> None:
    provider = DeterministicDiagnosticProvider()

    result = provider.generate(
        DiagnosticContext(
            session=_session(appliance_type="washer", symptoms=["leaking"], zip_code="76102"),
            user_message="It is still leaking.",
        )
    )

    assert result.status == DiagnosticSessionStatus.READY_TO_SCHEDULE
    assert result.recommended_action == "schedule_technician"
    assert result.tool_calls[0].name == "find_technician_matches"
    assert result.tool_calls[0].arguments == {
        "zip_code": "76102",
        "appliance_type": "washer",
    }


def test_openai_provider_uses_responses_api_contract() -> None:
    client = FakeClient()
    settings = Settings(openai_api_key="test", openai_model="gpt-test")
    session = _session()
    provider = OpenAIResponsesProvider(settings, client=client)

    result = provider.generate(DiagnosticContext(session=session, user_message="Please schedule."))

    assert client.responses.kwargs["model"] == "gpt-test"
    assert client.responses.kwargs["tools"][0]["name"] == "find_technician_matches"
    assert client.responses.kwargs["reasoning"] == {"effort": "low"}
    assert result.assistant_message == "I will check technician availability."
    assert result.recommended_action == "schedule_technician"
    assert result.tool_calls[0].arguments == {
        "zip_code": "75201",
        "appliance_type": "refrigerator",
    }


def test_openai_provider_defaults_message_when_response_has_no_text_or_tools() -> None:
    client = FakeClient(output_text="", output=[{"type": "message", "content": "ignored"}])
    settings = Settings(openai_api_key="test", openai_model="gpt-test")
    provider = OpenAIResponsesProvider(settings, client=client)

    result = provider.generate(DiagnosticContext(session=_session(), user_message="Hello."))

    assert result.status == DiagnosticSessionStatus.ACTIVE
    assert result.recommended_action is None
    assert result.tool_calls == []
    assert result.assistant_message == "I can help diagnose the issue and schedule service."


def test_openai_provider_reads_object_style_function_call_items() -> None:
    client = FakeClient(
        output=[
            SimpleNamespace(
                type="function_call",
                name="create_upload_link",
                arguments='{"session_id":42,"email":"customer@example.test"}',
            )
        ]
    )
    settings = Settings(openai_api_key="test", openai_model="gpt-test")
    provider = OpenAIResponsesProvider(settings, client=client)

    result = provider.generate(DiagnosticContext(session=_session(), user_message="Send upload."))

    assert result.status == DiagnosticSessionStatus.ACTIVE
    assert result.recommended_action is None
    assert result.tool_calls[0].name == "create_upload_link"
    assert result.tool_calls[0].arguments == {
        "session_id": 42,
        "email": "customer@example.test",
    }


def test_build_diagnostic_provider_selects_openai_or_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.agent.providers.OpenAIResponsesProvider",
        lambda settings: "openai-provider",
    )

    assert build_diagnostic_provider(Settings(openai_api_key="test")) == "openai-provider"
    provider = build_diagnostic_provider(Settings(openai_api_key=None))
    assert isinstance(provider, DeterministicDiagnosticProvider)


def test_troubleshooting_guidance_covers_supported_appliances_and_fallback() -> None:
    scenarios = [
        ("refrigerator", ["leaking"], "make sure the doors seal fully"),
        ("washer", ["not draining"], "confirm the lid or door is fully latched"),
        ("dryer", ["making noise"], "clean the lint screen"),
        ("dishwasher", ["not draining"], "remove visible food debris"),
        ("oven", ["not heating"], "confirm the control is set"),
        ("microwave", ["sparking"], "confirm the appliance has power"),
    ]

    for appliance_type, symptoms, expected_step in scenarios:
        guidance = troubleshooting_guidance(appliance_type, symptoms)

        assert guidance.startswith("Safe checks:")
        assert expected_step in guidance
