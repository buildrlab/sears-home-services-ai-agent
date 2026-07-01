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


def test_settings_accept_prefixed_environment_aliases(monkeypatch) -> None:
    monkeypatch.setenv("SHS_ENVIRONMENT", "ci")
    monkeypatch.setenv("SHS_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SHS_DATABASE_ECHO", "true")
    monkeypatch.setenv("SHS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SHS_OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("SHS_OPENAI_REASONING_EFFORT", "medium")
    monkeypatch.setenv("SHS_OPENAI_VERBOSITY", "medium")

    settings = Settings()

    assert settings.environment == "ci"
    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.database_echo is True
    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-test"
    assert settings.openai_reasoning_effort == "medium"
    assert settings.openai_verbosity == "medium"
