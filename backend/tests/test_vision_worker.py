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
