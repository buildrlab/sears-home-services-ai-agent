from __future__ import annotations

from app.config import DEFAULT_DATABASE_URL, Settings


def test_settings_use_secure_local_defaults() -> None:
    settings = Settings()

    assert settings.environment == "local"
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.database_echo is False
    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-5.5"
    assert settings.openai_reasoning_effort == "low"
    assert settings.openai_verbosity == "low"
    assert settings.openai_vision_model == "gpt-5.5"
    assert settings.twilio_auth_token is None
    assert settings.twilio_validate_requests is True
    assert settings.twilio_voice_mode == "gather"
    assert settings.twilio_conversation_relay_url == "wss://ws.shs.buildrlab.com/twilio/conversation"
    assert settings.public_base_url is None
    assert settings.aws_region == "us-east-1"
    assert settings.s3_upload_bucket == "shs-ai-agent-uploads-local"
    assert settings.upload_max_bytes == 10 * 1024 * 1024
    assert settings.email_delivery_mode == "smtp"
    assert settings.smtp_host == "127.0.0.1"
    assert settings.smtp_port == 1025


def test_settings_accept_prefixed_environment_aliases(monkeypatch) -> None:
    monkeypatch.setenv("SHS_ENVIRONMENT", "ci")
    monkeypatch.setenv("SHS_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SHS_DATABASE_ECHO", "true")
    monkeypatch.setenv("SHS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SHS_OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("SHS_OPENAI_REASONING_EFFORT", "medium")
    monkeypatch.setenv("SHS_OPENAI_VERBOSITY", "medium")
    monkeypatch.setenv("SHS_OPENAI_VISION_MODEL", "gpt-vision-test")
    monkeypatch.setenv("SHS_TWILIO_AUTH_TOKEN", "twilio-token")
    monkeypatch.setenv("SHS_TWILIO_VALIDATE_REQUESTS", "false")
    monkeypatch.setenv("SHS_TWILIO_VOICE_MODE", "conversationrelay")
    monkeypatch.setenv("SHS_TWILIO_CONVERSATION_RELAY_URL", "wss://ws.example.test/relay")
    monkeypatch.setenv("SHS_PUBLIC_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("SHS_AWS_REGION", "us-west-2")
    monkeypatch.setenv("SHS_S3_UPLOAD_BUCKET", "uploads-test")
    monkeypatch.setenv("SHS_S3_ENDPOINT_URL", "http://minio.test:9000")
    monkeypatch.setenv("SHS_UPLOAD_LINK_BASE_URL", "https://shs.example.test/upload")
    monkeypatch.setenv("SHS_UPLOAD_TOKEN_TTL_MINUTES", "30")
    monkeypatch.setenv("SHS_UPLOAD_MAX_BYTES", "1024")
    monkeypatch.setenv("SHS_EMAIL_DELIVERY_MODE", "ses")
    monkeypatch.setenv("SHS_EMAIL_FROM_ADDRESS", "no-reply@example.test")
    monkeypatch.setenv("SHS_SMTP_HOST", "mailpit")
    monkeypatch.setenv("SHS_SMTP_PORT", "2525")
    monkeypatch.setenv("SHS_SQS_VISION_QUEUE_URL", "https://sqs.test/queue")

    settings = Settings()

    assert settings.environment == "ci"
    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.database_echo is True
    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-test"
    assert settings.openai_reasoning_effort == "medium"
    assert settings.openai_verbosity == "medium"
    assert settings.openai_vision_model == "gpt-vision-test"
    assert settings.twilio_auth_token == "twilio-token"  # noqa: S105
    assert settings.twilio_validate_requests is False
    assert settings.twilio_voice_mode == "conversationrelay"
    assert settings.twilio_conversation_relay_url == "wss://ws.example.test/relay"
    assert settings.public_base_url == "https://api.example.test"
    assert settings.aws_region == "us-west-2"
    assert settings.s3_upload_bucket == "uploads-test"
    assert settings.s3_endpoint_url == "http://minio.test:9000"
    assert settings.upload_link_base_url == "https://shs.example.test/upload"
    assert settings.upload_token_ttl_minutes == 30
    assert settings.upload_max_bytes == 1024
    assert settings.email_delivery_mode == "ses"
    assert settings.email_from_address == "no-reply@example.test"
    assert settings.smtp_host == "mailpit"
    assert settings.smtp_port == 2525
    assert settings.sqs_vision_queue_url == "https://sqs.test/queue"
