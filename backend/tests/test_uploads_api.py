from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import (
    get_db_session,
    get_upload_email_sender,
    get_upload_storage_client,
    get_vision_provider,
    get_vision_queue,
)
from app.main import create_app
from app.services.storage import PresignedPost
from app.services.vision import (
    VisionAnalysisContext,
    VisionAnalysisResult,
)


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send_upload_link(self, *, to_email: str, upload_url: str, expires_at: datetime) -> None:
        self.sent.append(upload_url)


class FakeStorageClient:
    def create_presigned_post(
        self,
        *,
        bucket: str,
        key: str,
        content_type: str,
        max_bytes: int,
        expires_seconds: int,
    ) -> PresignedPost:
        return PresignedPost(
            url="https://s3.test/upload",
            fields={"key": key, "Content-Type": content_type},
        )

    def create_presigned_get_url(
        self,
        *,
        bucket: str,
        key: str,
        expires_seconds: int,
    ) -> str:
        return f"https://s3.test/{key}"


class FakeVisionQueue:
    def __init__(self) -> None:
        self.upload_ids: list[int] = []

    def enqueue(self, upload_id: int) -> None:
        self.upload_ids.append(upload_id)


class FakeVisionProvider:
    def analyze(self, context: VisionAnalysisContext) -> VisionAnalysisResult:
        return VisionAnalysisResult(
            summary="Image shows a visible refrigerator door gasket issue.",
            observations=["Door gasket appears loose."],
            recommended_action="schedule_technician",
        )


def _client(
    db_session: Session,
) -> tuple[TestClient, FakeEmailSender, FakeStorageClient, FakeVisionQueue]:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        upload_link_base_url="https://shs.example.test/upload",
        s3_upload_bucket="uploads-test",
        upload_max_bytes=1024,
        upload_allowed_content_types="image/jpeg,image/png",
    )
    app = create_app(settings)
    email_sender = FakeEmailSender()
    storage_client = FakeStorageClient()
    vision_queue = FakeVisionQueue()

    def override_session() -> Iterator[Session]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    def override_settings() -> Settings:
        return settings

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_upload_email_sender] = lambda: email_sender
    app.dependency_overrides[get_upload_storage_client] = lambda: storage_client
    app.dependency_overrides[get_vision_queue] = lambda: vision_queue
    app.dependency_overrides[get_vision_provider] = lambda: FakeVisionProvider()
    return TestClient(app), email_sender, storage_client, vision_queue


def test_upload_api_end_to_end_flow_updates_session_history(db_session: Session) -> None:
    client, email_sender, _, vision_queue = _client(db_session)
    session_response = client.post(
        "/diagnostics/sessions",
        json={"customer_phone": "+15551234567"},
    )
    session_id = session_response.json()["id"]

    link_response = client.post(
        f"/diagnostics/sessions/{session_id}/upload-link",
        json={"email": "caller@example.test"},
    )

    assert link_response.status_code == 201
    assert email_sender.sent == [link_response.json()["upload_url"]]
    token = link_response.json()["upload_url"].rsplit("/", 1)[-1]

    token_response = client.get(f"/uploads/{token}")
    assert token_response.status_code == 200
    assert token_response.json()["status"] == "pending_upload"

    presigned_response = client.post(
        f"/uploads/{token}/presigned-post",
        json={"filename": "fridge.png", "content_type": "image/png", "byte_size": 512},
    )
    assert presigned_response.status_code == 200
    assert presigned_response.json()["url"] == "https://s3.test/upload"
    assert presigned_response.json()["fields"]["Content-Type"] == "image/png"

    complete_response = client.post(
        f"/uploads/{token}/complete",
        json={"filename": "fridge.png", "content_type": "image/png", "byte_size": 512},
    )
    assert complete_response.status_code == 200
    upload_id = complete_response.json()["id"]
    assert complete_response.json()["status"] == "analysis_pending"
    assert vision_queue.upload_ids == [upload_id]

    analysis_response = client.post(f"/diagnostics/uploads/{upload_id}/analysis")
    assert analysis_response.status_code == 200
    assert analysis_response.json()["status"] == "analyzed"
    assert "door gasket" in analysis_response.json()["analysis_summary"]

    uploads_response = client.get(f"/diagnostics/sessions/{session_id}/uploads")
    assert uploads_response.status_code == 200
    assert uploads_response.json()["uploads"][0]["id"] == upload_id

    session_fetch_response = client.get(f"/diagnostics/sessions/{session_id}")
    event_contents = [event["content"] for event in session_fetch_response.json()["events"]]
    assert any("Image analysis completed" in content for content in event_contents)


def test_upload_api_rejects_unsupported_content_type(db_session: Session) -> None:
    client, _, _, _ = _client(db_session)
    session_response = client.post("/diagnostics/sessions", json={})
    session_id = session_response.json()["id"]
    link_response = client.post(
        f"/diagnostics/sessions/{session_id}/upload-link",
        json={"email": "caller@example.test"},
    )
    token = link_response.json()["upload_url"].rsplit("/", 1)[-1]

    response = client.post(
        f"/uploads/{token}/presigned-post",
        json={"filename": "payload.svg", "content_type": "image/svg+xml", "byte_size": 10},
    )

    assert response.status_code == 422
