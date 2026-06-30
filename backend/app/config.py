"""Runtime configuration for the backend service."""

from __future__ import annotations

from functools import lru_cache

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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
