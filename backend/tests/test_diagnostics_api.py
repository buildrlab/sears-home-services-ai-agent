from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_db_session
from app.main import create_app


def _client(db_session: Session) -> TestClient:
    app = create_app(Settings(environment="test", database_url="sqlite+pysqlite:///:memory:"))

    def override_session() -> Iterator[Session]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    def override_settings() -> Settings:
        return Settings(environment="test", database_url="sqlite+pysqlite:///:memory:")

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    return TestClient(app)


def test_diagnostic_api_scripted_call_flow(db_session: Session) -> None:
    client = _client(db_session)

    create_response = client.post(
        "/diagnostics/sessions",
        json={"customer_phone": "+15551234567"},
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["id"]

    first_turn = client.post(
        f"/diagnostics/sessions/{session_id}/turn",
        json={"message": "My refrigerator is not cooling."},
    )
    assert first_turn.status_code == 200
    assert first_turn.json()["session"]["appliance_type"] == "refrigerator"
    assert first_turn.json()["session"]["symptoms"] == ["not cooling"]
    assert "What ZIP code" in first_turn.json()["assistant_message"]

    second_turn = client.post(
        f"/diagnostics/sessions/{session_id}/turn",
        json={"message": "It is in 75201."},
    )
    assert second_turn.status_code == 200
    assert second_turn.json()["session"]["status"] == "ready_to_schedule"
    assert second_turn.json()["tool_calls"] == [
        {
            "name": "find_technician_matches",
            "arguments": {"zip_code": "75201", "appliance_type": "refrigerator"},
        }
    ]


def test_diagnostic_api_returns_404_for_missing_session(db_session: Session) -> None:
    client = _client(db_session)

    response = client.post("/diagnostics/sessions/999/turn", json={"message": "hello"})

    assert response.status_code == 404
