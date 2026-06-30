from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_healthz_returns_runtime_status() -> None:
    app = create_app(Settings(environment="test", database_url="sqlite+pysqlite:///:memory:"))
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "shs-ai-agent-backend",
        "environment": "test",
    }
