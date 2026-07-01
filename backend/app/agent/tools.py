"""Diagnostic agent tool schemas and validation."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class ToolName(StrEnum):
    FIND_TECHNICIAN_MATCHES = "find_technician_matches"
    CREATE_UPLOAD_LINK = "create_upload_link"
    UPDATE_CALL_STATE = "update_call_state"


class FindTechnicianMatchesArgs(BaseModel):
    zip_code: str = Field(min_length=5, max_length=10)
    appliance_type: str = Field(min_length=1, max_length=80)


class CreateUploadLinkArgs(BaseModel):
    session_id: int = Field(gt=0)
    email: str = Field(min_length=3, max_length=255)


class UpdateCallStateArgs(BaseModel):
    appliance_type: str | None = Field(default=None, max_length=80)
    symptoms: list[str] = Field(default_factory=list)
    zip_code: str | None = Field(default=None, min_length=5, max_length=10)
    safety_blocked: bool = False


class AgentToolCall(BaseModel):
    name: ToolName
    arguments: dict[str, Any]


class ToolValidationError(ValueError):
    """Raised when a requested agent tool call does not match its schema."""


TOOL_SCHEMAS: dict[ToolName, type[BaseModel]] = {
    ToolName.FIND_TECHNICIAN_MATCHES: FindTechnicianMatchesArgs,
    ToolName.CREATE_UPLOAD_LINK: CreateUploadLinkArgs,
    ToolName.UPDATE_CALL_STATE: UpdateCallStateArgs,
}

OPENAI_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": ToolName.FIND_TECHNICIAN_MATCHES.value,
        "description": "Find Sears Home Services technicians by ZIP code and appliance type.",
        "parameters": FindTechnicianMatchesArgs.model_json_schema(),
    },
    {
        "type": "function",
        "name": ToolName.CREATE_UPLOAD_LINK.value,
        "description": "Create a secure appliance image upload link for the caller.",
        "parameters": CreateUploadLinkArgs.model_json_schema(),
    },
    {
        "type": "function",
        "name": ToolName.UPDATE_CALL_STATE.value,
        "description": "Persist extracted diagnostic call state.",
        "parameters": UpdateCallStateArgs.model_json_schema(),
    },
]


def validate_tool_call(name: str, arguments: dict[str, Any] | str) -> AgentToolCall:
    try:
        tool_name = ToolName(name)
    except ValueError as exc:
        raise ToolValidationError(f"Unsupported tool call: {name}") from exc

    parsed_arguments = _parse_arguments(arguments)
    schema = TOOL_SCHEMAS[tool_name]
    try:
        validated = schema.model_validate(parsed_arguments)
    except ValidationError as exc:
        raise ToolValidationError(f"Invalid arguments for {tool_name.value}: {exc}") from exc
    return AgentToolCall(name=tool_name, arguments=validated.model_dump())


def _parse_arguments(arguments: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ToolValidationError("Tool arguments must be a JSON object.") from exc
    if not isinstance(parsed, dict):
        raise ToolValidationError("Tool arguments must be a JSON object.")
    return parsed
