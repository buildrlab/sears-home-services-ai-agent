"""FastAPI dependency helpers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import session_scope
from app.services.email import UploadEmailSender, build_upload_email_sender
from app.services.storage import UploadStorageClient, build_upload_storage_client
from app.services.vision import (
    VisionAnalysisProvider,
    VisionQueue,
    build_vision_analysis_provider,
    build_vision_queue,
)


def get_db_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session


def get_upload_storage_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadStorageClient:
    return build_upload_storage_client(settings)


def get_upload_email_sender(
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadEmailSender:
    return build_upload_email_sender(settings)


def get_vision_queue(settings: Annotated[Settings, Depends(get_settings)]) -> VisionQueue:
    return build_vision_queue(settings)


def get_vision_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> VisionAnalysisProvider:
    return build_vision_analysis_provider(settings)
