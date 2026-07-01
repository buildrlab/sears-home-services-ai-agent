"""Runtime configuration for the backend service."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://shs:shs_local_password@localhost:5432/shs_ai_agent"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Sears Home Services AI Agent"
    environment: str = Field(
        default="local",
        validation_alias=AliasChoices("ENVIRONMENT", "SHS_ENVIRONMENT"),
    )
    database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias=AliasChoices("DATABASE_URL", "SHS_DATABASE_URL"),
    )
    database_echo: bool = Field(
        default=False,
        validation_alias=AliasChoices("DATABASE_ECHO", "SHS_DATABASE_ECHO"),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "SHS_OPENAI_API_KEY"),
    )
    openai_model: str = Field(
        default="gpt-5.5",
        validation_alias=AliasChoices("OPENAI_MODEL", "SHS_OPENAI_MODEL"),
    )
    openai_reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = Field(
        default="low",
        validation_alias=AliasChoices(
            "OPENAI_REASONING_EFFORT",
            "SHS_OPENAI_REASONING_EFFORT",
        ),
    )
    openai_verbosity: Literal["low", "medium", "high"] = Field(
        default="low",
        validation_alias=AliasChoices("OPENAI_VERBOSITY", "SHS_OPENAI_VERBOSITY"),
    )
    twilio_auth_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_AUTH_TOKEN", "SHS_TWILIO_AUTH_TOKEN"),
    )
    twilio_validate_requests: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "TWILIO_VALIDATE_REQUESTS",
            "SHS_TWILIO_VALIDATE_REQUESTS",
        ),
    )
    twilio_voice_mode: Literal["gather", "conversationrelay"] = Field(
        default="gather",
        validation_alias=AliasChoices("TWILIO_VOICE_MODE", "SHS_TWILIO_VOICE_MODE"),
    )
    twilio_conversation_relay_url: str = Field(
        default="wss://ws.shs.buildrlab.com/twilio/conversation",
        validation_alias=AliasChoices(
            "TWILIO_CONVERSATION_RELAY_URL",
            "SHS_TWILIO_CONVERSATION_RELAY_URL",
        ),
    )
    public_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUBLIC_BASE_URL", "SHS_PUBLIC_BASE_URL"),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
