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
    openai_vision_model: str = Field(
        default="gpt-5.5",
        validation_alias=AliasChoices("OPENAI_VISION_MODEL", "SHS_OPENAI_VISION_MODEL"),
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
    aws_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("AWS_REGION", "SHS_AWS_REGION"),
    )
    aws_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AWS_ACCESS_KEY_ID", "SHS_AWS_ACCESS_KEY_ID"),
    )
    aws_secret_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AWS_SECRET_ACCESS_KEY", "SHS_AWS_SECRET_ACCESS_KEY"),
    )
    s3_upload_bucket: str = Field(
        default="shs-ai-agent-uploads-local",
        validation_alias=AliasChoices("S3_UPLOAD_BUCKET", "SHS_S3_UPLOAD_BUCKET"),
    )
    s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_ENDPOINT_URL", "SHS_S3_ENDPOINT_URL"),
    )
    s3_presign_expires_seconds: int = Field(
        default=900,
        validation_alias=AliasChoices(
            "S3_PRESIGN_EXPIRES_SECONDS",
            "SHS_S3_PRESIGN_EXPIRES_SECONDS",
        ),
    )
    upload_link_base_url: str = Field(
        default="http://127.0.0.1:8000/uploads",
        validation_alias=AliasChoices("UPLOAD_LINK_BASE_URL", "SHS_UPLOAD_LINK_BASE_URL"),
    )
    upload_token_ttl_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices("UPLOAD_TOKEN_TTL_MINUTES", "SHS_UPLOAD_TOKEN_TTL_MINUTES"),
    )
    upload_max_bytes: int = Field(
        default=10 * 1024 * 1024,
        validation_alias=AliasChoices("UPLOAD_MAX_BYTES", "SHS_UPLOAD_MAX_BYTES"),
    )
    upload_allowed_content_types: str = Field(
        default="image/jpeg,image/png,image/webp",
        validation_alias=AliasChoices(
            "UPLOAD_ALLOWED_CONTENT_TYPES",
            "SHS_UPLOAD_ALLOWED_CONTENT_TYPES",
        ),
    )
    email_delivery_mode: Literal["smtp", "ses"] = Field(
        default="smtp",
        validation_alias=AliasChoices("EMAIL_DELIVERY_MODE", "SHS_EMAIL_DELIVERY_MODE"),
    )
    email_from_address: str = Field(
        default="Sears Home Services <no-reply@shs.buildrlab.com>",
        validation_alias=AliasChoices("EMAIL_FROM_ADDRESS", "SHS_EMAIL_FROM_ADDRESS"),
    )
    smtp_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("SMTP_HOST", "SHS_SMTP_HOST"),
    )
    smtp_port: int = Field(
        default=1025,
        validation_alias=AliasChoices("SMTP_PORT", "SHS_SMTP_PORT"),
    )
    sqs_vision_queue_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQS_VISION_QUEUE_URL", "SHS_SQS_VISION_QUEUE_URL"),
    )
    vision_presigned_get_expires_seconds: int = Field(
        default=600,
        validation_alias=AliasChoices(
            "VISION_PRESIGNED_GET_EXPIRES_SECONDS",
            "SHS_VISION_PRESIGNED_GET_EXPIRES_SECONDS",
        ),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
