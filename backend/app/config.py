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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
