from __future__ import annotations

from app.config import DEFAULT_DATABASE_URL, Settings


def test_settings_use_secure_local_defaults() -> None:
    settings = Settings()

    assert settings.environment == "local"
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.database_echo is False


def test_settings_accept_prefixed_environment_aliases(monkeypatch) -> None:
    monkeypatch.setenv("SHS_ENVIRONMENT", "ci")
    monkeypatch.setenv("SHS_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SHS_DATABASE_ECHO", "true")

    settings = Settings()

    assert settings.environment == "ci"
    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.database_echo is True
