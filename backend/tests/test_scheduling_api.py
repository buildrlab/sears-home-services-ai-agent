from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_db_session
from app.main import create_app
from app.seed import seed_reference_data


def _client(db_session: Session) -> TestClient:
    seed_reference_data(db_session)
    db_session.commit()
    app = create_app(Settings(environment="test", database_url="sqlite+pysqlite:///:memory:"))

    def override_session() -> Iterator[Session]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app)


def _hold_payload() -> dict[str, object]:
    return {
        "customer": {
            "full_name": "Jordan Customer",
            "email": "jordan.api@example.test",
            "phone": "+15551234567",
        },
        "technician_id": 1,
        "appliance_type": "refrigerator",
        "zip_code": "75201",
        "scheduled_start": "2026-07-06T08:00:00+00:00",
        "issue_summary": "Refrigerator is not cooling.",
    }


def test_find_matches_endpoint_returns_seeded_technicians(db_session: Session) -> None:
    client = _client(db_session)

    response = client.get(
        "/scheduling/matches",
        params={"zip_code": "75201", "appliance_type": "refrigerator"},
    )

    assert response.status_code == 200
    assert response.json()["matches"][0]["name"] == "Avery Johnson"


def test_find_matches_endpoint_returns_empty_list_for_no_match(db_session: Session) -> None:
    client = _client(db_session)

    response = client.get(
        "/scheduling/matches",
        params={"zip_code": "99999", "appliance_type": "refrigerator"},
    )

    assert response.status_code == 200
    assert response.json() == {"matches": []}


def test_appointment_hold_book_and_fetch_flow(db_session: Session) -> None:
    client = _client(db_session)

    hold_response = client.post("/appointments/holds", json=_hold_payload())
    assert hold_response.status_code == 201
    appointment_id = hold_response.json()["id"]
    assert hold_response.json()["status"] == "held"

    book_response = client.post(f"/appointments/{appointment_id}/book")
    assert book_response.status_code == 200
    assert book_response.json()["status"] == "booked"
    assert book_response.json()["confirmation_code"].startswith("SHS-")

    fetch_response = client.get(f"/appointments/{appointment_id}")
    assert fetch_response.status_code == 200
    assert fetch_response.json()["confirmation_code"] == book_response.json()["confirmation_code"]


def test_appointment_hold_endpoint_conflicts_on_double_book(db_session: Session) -> None:
    client = _client(db_session)

    first_response = client.post("/appointments/holds", json=_hold_payload())
    second_payload = _hold_payload()
    second_payload["customer"] = {
        "full_name": "Second Customer",
        "email": "second.api@example.test",
        "phone": "+15557654321",
    }
    second_response = client.post("/appointments/holds", json=second_payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_appointment_hold_endpoint_rejects_naive_datetime(db_session: Session) -> None:
    client = _client(db_session)
    payload = _hold_payload()
    payload["scheduled_start"] = "2026-07-06T08:00:00"

    response = client.post("/appointments/holds", json=payload)

    assert response.status_code == 422
