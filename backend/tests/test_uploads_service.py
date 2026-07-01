from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ImageUploadStatus
from app.schemas import DiagnosticSessionCreate
from app.services.diagnostics import DiagnosticService
from app.services.email import render_upload_email
from app.services.storage import PresignedPost
from app.services.uploads import (
    UploadService,
    UploadTokenExpiredError,
    UploadValidationError,
    hash_upload_token,
)
from app.services.vision import (
    VisionAnalysisContext,
    VisionAnalysisResult,
    VisionAnalysisService,
)


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    def send_upload_link(self, *, to_email: str, upload_url: str, expires_at: datetime) -> None:
        self.sent.append(
            {"to_email": to_email, "upload_url": upload_url, "expires_at": expires_at}
        )


class FakeStorageClient:
    def __init__(self) -> None:
        self.posts: list[dict[str, object]] = []
        self.gets: list[dict[str, object]] = []

    def create_presigned_post(
        self,
        *,
        bucket: str,
        key: str,
        content_type: str,
        max_bytes: int,
        expires_seconds: int,
    ) -> PresignedPost:
        self.posts.append(
            {
                "bucket": bucket,
                "key": key,
                "content_type": content_type,
                "max_bytes": max_bytes,
                "expires_seconds": expires_seconds,
            }
        )
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
        self.gets.append({"bucket": bucket, "key": key, "expires_seconds": expires_seconds})
        return f"https://s3.test/{key}"


class FakeVisionQueue:
    def __init__(self) -> None:
        self.upload_ids: list[int] = []

    def enqueue(self, upload_id: int) -> None:
        self.upload_ids.append(upload_id)


class FakeVisionProvider:
    def analyze(self, context: VisionAnalysisContext) -> VisionAnalysisResult:
        return VisionAnalysisResult(
            summary=f"Visible issue confirmed for {context.appliance_type}.",
            observations=["Door gasket appears damaged."],
            recommended_action="schedule_technician",
        )


class FailingVisionProvider:
    def analyze(self, context: VisionAnalysisContext) -> VisionAnalysisResult:
        raise RuntimeError("vision provider unavailable")


def _settings() -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        s3_upload_bucket="uploads-test",
        upload_link_base_url="https://shs.example.test/upload",
        upload_token_ttl_minutes=30,
        upload_max_bytes=1024,
        upload_allowed_content_types="image/jpeg,image/png",
    )


def _diagnostic_session(db_session: Session):
    return DiagnosticService(db_session, _settings()).create_session(
        DiagnosticSessionCreate(
            customer_phone="+15551234567",
            customer_email="caller@example.test",
        )
    )


def _upload_service(
    db_session: Session,
    *,
    email_sender: FakeEmailSender | None = None,
    storage_client: FakeStorageClient | None = None,
    vision_queue: FakeVisionQueue | None = None,
) -> tuple[UploadService, FakeEmailSender, FakeStorageClient, FakeVisionQueue]:
    email_sender = email_sender or FakeEmailSender()
    storage_client = storage_client or FakeStorageClient()
    vision_queue = vision_queue or FakeVisionQueue()
    return (
        UploadService(db_session, _settings(), storage_client, email_sender, vision_queue),
        email_sender,
        storage_client,
        vision_queue,
    )


def test_create_upload_link_hashes_token_and_sends_email(db_session: Session) -> None:
    diagnostic_session = _diagnostic_session(db_session)
    service, email_sender, _, _ = _upload_service(db_session)

    result = service.create_upload_link(
        session_id=diagnostic_session.id,
        email="Caller@Example.Test",
    )

    assert result.upload_url.startswith("https://shs.example.test/upload/")
    assert result.token not in result.upload.token_hash
    assert result.upload.token_hash == hash_upload_token(result.token)
    assert result.upload.status == ImageUploadStatus.PENDING_UPLOAD.value
    assert diagnostic_session.customer_email == "caller@example.test"
    assert email_sender.sent[0]["to_email"] == "caller@example.test"
    assert "caller@example.test" not in diagnostic_session.events[-1].tool_payload["email"]


def test_upload_token_expiry_marks_record_expired(db_session: Session) -> None:
    diagnostic_session = _diagnostic_session(db_session)
    service, _, _, _ = _upload_service(db_session)
    result = service.create_upload_link(session_id=diagnostic_session.id, email="a@example.test")
    result.upload.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.flush()

    with pytest.raises(UploadTokenExpiredError):
        service.get_upload_by_token(result.token)

    assert result.upload.status == ImageUploadStatus.EXPIRED.value


def test_presigned_post_validates_file_type_and_size(db_session: Session) -> None:
    diagnostic_session = _diagnostic_session(db_session)
    service, _, storage_client, _ = _upload_service(db_session)
    result = service.create_upload_link(session_id=diagnostic_session.id, email="a@example.test")

    presigned = service.create_presigned_post(
        token=result.token,
        filename="../fridge.jpg",
        content_type="image/jpeg",
        byte_size=512,
    )

    assert presigned.url == "https://s3.test/upload"
    assert presigned.fields["Content-Type"] == "image/jpeg"
    assert result.upload.original_filename == "fridge.jpg"
    assert storage_client.posts[0]["max_bytes"] == 1024

    with pytest.raises(UploadValidationError):
        service.create_presigned_post(
            token=result.token,
            filename="script.svg",
            content_type="image/svg+xml",
            byte_size=10,
        )

    with pytest.raises(UploadValidationError):
        service.create_presigned_post(
            token=result.token,
            filename="large.jpg",
            content_type="image/jpeg",
            byte_size=2048,
        )


def test_complete_upload_marks_analysis_pending_and_queues_worker(db_session: Session) -> None:
    diagnostic_session = _diagnostic_session(db_session)
    service, _, _, vision_queue = _upload_service(db_session)
    result = service.create_upload_link(session_id=diagnostic_session.id, email="a@example.test")

    upload = service.complete_upload(
        token=result.token,
        filename="fridge.png",
        content_type="image/png",
        byte_size=512,
    )

    assert upload.status == ImageUploadStatus.ANALYSIS_PENDING.value
    assert upload.uploaded_at is not None
    assert vision_queue.upload_ids == [upload.id]


def test_vision_analysis_success_attaches_result_to_session_history(db_session: Session) -> None:
    diagnostic_session = _diagnostic_session(db_session)
    diagnostic_session.appliance_type = "refrigerator"
    diagnostic_session.symptoms = ["leaking"]
    service, _, storage_client, _ = _upload_service(db_session)
    result = service.create_upload_link(session_id=diagnostic_session.id, email="a@example.test")
    upload = service.complete_upload(
        token=result.token,
        filename="fridge.png",
        content_type="image/png",
        byte_size=512,
    )

    analyzed = VisionAnalysisService(
        db_session,
        _settings(),
        storage_client,
        FakeVisionProvider(),
    ).process_upload(upload.id)

    assert analyzed.status == ImageUploadStatus.ANALYZED.value
    assert analyzed.analysis_summary == "Visible issue confirmed for refrigerator."
    assert storage_client.gets[0]["key"] == analyzed.storage_key
    assert diagnostic_session.events[-1].tool_name == "analyze_image"
    assert "Visible issue confirmed" in diagnostic_session.events[-1].content


def test_vision_analysis_failure_marks_upload_failed(db_session: Session) -> None:
    diagnostic_session = _diagnostic_session(db_session)
    service, _, storage_client, _ = _upload_service(db_session)
    result = service.create_upload_link(session_id=diagnostic_session.id, email="a@example.test")
    upload = service.complete_upload(
        token=result.token,
        filename="fridge.png",
        content_type="image/png",
        byte_size=512,
    )

    processed = VisionAnalysisService(
        db_session,
        _settings(),
        storage_client,
        FailingVisionProvider(),
    ).process_upload(upload.id)

    assert processed.status == ImageUploadStatus.FAILED.value
    assert processed.failure_reason == "vision provider unavailable"
    assert diagnostic_session.events[-1].tool_name == "analyze_image_failed"


def test_render_upload_email_includes_link_and_expiry() -> None:
    expires_at = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    rendered = render_upload_email(
        upload_url="https://shs.example.test/upload/token?x=<bad>",
        expires_at=expires_at,
    )

    assert rendered.subject == "Sears Home Services appliance photo upload"
    assert "https://shs.example.test/upload/token?x=<bad>" in rendered.text_body
    assert "x=&lt;bad&gt;" in rendered.html_body
    assert expires_at.isoformat() in rendered.text_body
