from __future__ import annotations

import pytest

from app.agent.extraction import (
    extract_appliance_type,
    extract_email,
    extract_symptoms,
    extract_zip_code,
    requests_image_upload,
)
from app.agent.tools import ToolName, ToolValidationError, validate_tool_call


def test_extracts_appliance_symptoms_and_zip() -> None:
    message = "My fridge is warm and leaking in 75201."

    assert extract_appliance_type(message) == "refrigerator"
    assert extract_symptoms(message) == ["not cooling", "leaking"]
    assert extract_zip_code(message) == "75201"


def test_symptom_extraction_preserves_memory_without_duplicates() -> None:
    symptoms = extract_symptoms("The washer is leaking.", existing=["leaking"])

    assert symptoms == ["leaking"]


def test_extractors_return_empty_state_when_message_has_no_supported_data() -> None:
    message = "Hello, I need help later."

    assert extract_appliance_type(message) is None
    assert extract_symptoms(message) == []
    assert extract_zip_code(message) is None
    assert extract_email(message) is None
    assert requests_image_upload(message) is False


def test_extracts_email_and_upload_intent() -> None:
    message = "Please send the picture upload link to Customer@Example.Test."

    assert extract_email(message) == "customer@example.test"
    assert requests_image_upload(message) is True


def test_validate_tool_call_accepts_known_tool_schema() -> None:
    tool_call = validate_tool_call(
        ToolName.FIND_TECHNICIAN_MATCHES.value,
        {"zip_code": "75201", "appliance_type": "refrigerator"},
    )

    assert tool_call.name == ToolName.FIND_TECHNICIAN_MATCHES
    assert tool_call.arguments == {"zip_code": "75201", "appliance_type": "refrigerator"}


def test_validate_tool_call_rejects_unknown_tool() -> None:
    with pytest.raises(ToolValidationError, match="Unsupported tool"):
        validate_tool_call("delete_database", {})


def test_validate_tool_call_rejects_bad_arguments() -> None:
    with pytest.raises(ToolValidationError, match="Invalid arguments"):
        validate_tool_call(ToolName.FIND_TECHNICIAN_MATCHES.value, {"zip_code": "1"})


def test_validate_tool_call_rejects_invalid_json_argument_text() -> None:
    with pytest.raises(ToolValidationError, match="JSON object"):
        validate_tool_call(ToolName.FIND_TECHNICIAN_MATCHES.value, "{not-json")


def test_validate_tool_call_rejects_non_object_json_argument_text() -> None:
    with pytest.raises(ToolValidationError, match="JSON object"):
        validate_tool_call(ToolName.FIND_TECHNICIAN_MATCHES.value, '["75201"]')
