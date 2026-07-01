from __future__ import annotations

from types import SimpleNamespace

from app.agent.providers import DiagnosticContext, OpenAIResponsesProvider
from app.config import Settings
from app.models import DiagnosticSession


class FakeResponses:
    def __init__(self) -> None:
        self.kwargs = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            output_text="I will check technician availability.",
            output=[
                {
                    "type": "function_call",
                    "name": "find_technician_matches",
                    "arguments": '{"zip_code":"75201","appliance_type":"refrigerator"}',
                }
            ],
        )


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def test_openai_provider_uses_responses_api_contract() -> None:
    client = FakeClient()
    settings = Settings(openai_api_key="test", openai_model="gpt-test")
    session = DiagnosticSession(
        id=1,
        appliance_type="refrigerator",
        symptoms=["not cooling"],
        zip_code="75201",
        safety_blocked=False,
    )
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
