from __future__ import annotations

import pytest

from app.config import Settings
from app.workers import vision


class FakeSessionScope:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


class FakeVisionAnalysisService:
    processed: list[int] = []

    def __init__(self, session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def process_upload(self, upload_id: int) -> None:
        self.processed.append(upload_id)


class FakeSqsClient:
    def __init__(self) -> None:
        self.deleted_receipts: list[str] = []

    def receive_message(self, **kwargs):
        assert kwargs["QueueUrl"] == "https://sqs.test/queue"
        assert kwargs["MaxNumberOfMessages"] == 5
        assert kwargs["WaitTimeSeconds"] == 1
        assert kwargs["VisibilityTimeout"] == 30
        return {
            "Messages": [
                {
                    "Body": '{"image_upload_id": 77}',
                    "ReceiptHandle": "receipt-77",
                }
            ]
        }

    def delete_message(self, **kwargs) -> None:
        assert kwargs["QueueUrl"] == "https://sqs.test/queue"
        self.deleted_receipts.append(kwargs["ReceiptHandle"])


def test_process_message_body_invokes_vision_service(monkeypatch) -> None:
    FakeVisionAnalysisService.processed = []
    monkeypatch.setattr(vision, "session_scope", lambda: FakeSessionScope())
    monkeypatch.setattr(vision, "get_settings", lambda: Settings(environment="test"))
    monkeypatch.setattr(vision, "VisionAnalysisService", FakeVisionAnalysisService)

    processed_upload_id = vision.process_message_body('{"image_upload_id": 42}')

    assert processed_upload_id == 42
    assert FakeVisionAnalysisService.processed == [42]


def test_process_message_body_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError, match="image_upload_id"):
        vision.process_message_body('{"missing": 42}')


def test_poll_sqs_processes_and_deletes_message(monkeypatch) -> None:
    FakeVisionAnalysisService.processed = []
    fake_client = FakeSqsClient()
    monkeypatch.setattr(vision, "session_scope", lambda: FakeSessionScope())
    monkeypatch.setattr(vision, "get_settings", lambda: Settings(environment="test"))
    monkeypatch.setattr(vision, "VisionAnalysisService", FakeVisionAnalysisService)

    processed_count = vision.poll_sqs(
        Settings(environment="test", sqs_vision_queue_url="https://sqs.test/queue"),
        once=True,
        wait_time_seconds=1,
        max_number_of_messages=5,
        visibility_timeout=30,
        client=fake_client,
    )

    assert processed_count == 1
    assert FakeVisionAnalysisService.processed == [77]
    assert fake_client.deleted_receipts == ["receipt-77"]


def test_poll_sqs_requires_queue_url() -> None:
    with pytest.raises(ValueError, match="SQS_VISION_QUEUE_URL"):
        vision.poll_sqs(
            Settings(environment="test"),
            once=True,
            wait_time_seconds=1,
            max_number_of_messages=1,
            visibility_timeout=30,
            client=FakeSqsClient(),
        )
