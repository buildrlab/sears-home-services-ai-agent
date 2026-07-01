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
    assert settings.twilio_auth_token is None
    assert settings.twilio_validate_requests is True
    assert settings.twilio_voice_mode == "gather"
    assert settings.twilio_conversation_relay_url == "wss://ws.shs.buildrlab.com/twilio/conversation"
    assert settings.public_base_url is None


def test_settings_accept_prefixed_environment_aliases(monkeypatch) -> None:
    monkeypatch.setenv("SHS_ENVIRONMENT", "ci")
    monkeypatch.setenv("SHS_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SHS_DATABASE_ECHO", "true")
    monkeypatch.setenv("SHS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SHS_OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("SHS_OPENAI_REASONING_EFFORT", "medium")
    monkeypatch.setenv("SHS_OPENAI_VERBOSITY", "medium")
    monkeypatch.setenv("SHS_TWILIO_AUTH_TOKEN", "twilio-token")
    monkeypatch.setenv("SHS_TWILIO_VALIDATE_REQUESTS", "false")
    monkeypatch.setenv("SHS_TWILIO_VOICE_MODE", "conversationrelay")
    monkeypatch.setenv("SHS_TWILIO_CONVERSATION_RELAY_URL", "wss://ws.example.test/relay")
    monkeypatch.setenv("SHS_PUBLIC_BASE_URL", "https://api.example.test")

    settings = Settings()

    assert settings.environment == "ci"
    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.database_echo is True
    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-test"
    assert settings.openai_reasoning_effort == "medium"
    assert settings.openai_verbosity == "medium"
    assert settings.twilio_auth_token == "twilio-token"  # noqa: S105
    assert settings.twilio_validate_requests is False
    assert settings.twilio_voice_mode == "conversationrelay"
    assert settings.twilio_conversation_relay_url == "wss://ws.example.test/relay"
    assert settings.public_base_url == "https://api.example.test"
