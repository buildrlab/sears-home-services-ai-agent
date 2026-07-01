"""Secure appliance image upload workflow."""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.exceptions import DiagnosticSessionNotFoundError
from app.models import (
    DiagnosticEvent,
    DiagnosticEventRole,
    DiagnosticSession,
    ImageUpload,
    ImageUploadStatus,
)
from app.services.email import UploadEmailSender, build_upload_email_sender
from app.services.storage import PresignedPost, UploadStorageClient, build_upload_storage_client
from app.services.vision import VisionQueue, build_vision_queue

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class UploadLinkResult:
    upload: ImageUpload
    token: str
    upload_url: str
    email_sent: bool


class UploadService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        storage_client: UploadStorageClient | None = None,
        email_sender: UploadEmailSender | None = None,
        vision_queue: VisionQueue | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage_client = storage_client or build_upload_storage_client(settings)
        self._email_sender = email_sender or build_upload_email_sender(settings)
        self._vision_queue = vision_queue or build_vision_queue(settings)

    def create_upload_link(self, *, session_id: int, email: str) -> UploadLinkResult:
        diagnostic_session = self._get_diagnostic_session(session_id)
        normalized_email = normalize_email(email)
        token = secrets.token_urlsafe(32)
        upload = ImageUpload(
            diagnostic_session_id=diagnostic_session.id,
            token_hash=hash_upload_token(token),
            storage_bucket=self._settings.s3_upload_bucket,
            storage_key=f"diagnostic-sessions/{diagnostic_session.id}/uploads/{uuid.uuid4().hex}",
            status=ImageUploadStatus.PENDING_UPLOAD.value,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=self._settings.upload_token_ttl_minutes),
        )
        diagnostic_session.customer_email = normalized_email
        self._session.add(upload)
        self._session.flush()

        upload_url = build_upload_url(self._settings, token)
        self._email_sender.send_upload_link(
            to_email=normalized_email,
            upload_url=upload_url,
            expires_at=upload.expires_at,
        )
        self._session.add(
            DiagnosticEvent(
                session=diagnostic_session,
                role=DiagnosticEventRole.TOOL.value,
                content="Secure appliance image upload link sent.",
                tool_name="create_upload_link",
                tool_payload={
                    "image_upload_id": upload.id,
                    "email": redact_email(normalized_email),
                    "expires_at": upload.expires_at.isoformat(),
                },
            )
        )
        self._session.flush()
        return UploadLinkResult(upload=upload, token=token, upload_url=upload_url, email_sent=True)

    def get_upload_by_token(self, token: str) -> ImageUpload:
        upload = self._find_upload_by_token(token)
        self._mark_expired_if_needed(upload)
        if upload.status == ImageUploadStatus.EXPIRED.value:
            raise UploadTokenExpiredError("Upload token has expired.")
        return upload

    def create_presigned_post(
        self,
        *,
        token: str,
        filename: str,
        content_type: str,
        byte_size: int,
    ) -> PresignedPost:
        upload = self.get_upload_by_token(token)
        validate_upload_metadata(
            settings=self._settings,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
        )
        upload.original_filename = sanitize_filename(filename)
        upload.content_type = content_type
        upload.byte_size = byte_size
        self._session.flush()
        return self._storage_client.create_presigned_post(
            bucket=upload.storage_bucket,
            key=upload.storage_key,
            content_type=content_type,
            max_bytes=self._settings.upload_max_bytes,
            expires_seconds=self._settings.s3_presign_expires_seconds,
        )

    def complete_upload(
        self,
        *,
        token: str,
        filename: str,
        content_type: str,
        byte_size: int,
    ) -> ImageUpload:
        upload = self.get_upload_by_token(token)
        validate_upload_metadata(
            settings=self._settings,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
        )
        upload.original_filename = sanitize_filename(filename)
        upload.content_type = content_type
        upload.byte_size = byte_size
        upload.status = ImageUploadStatus.ANALYSIS_PENDING.value
        upload.uploaded_at = datetime.now(UTC)
        self._session.add(
            DiagnosticEvent(
                session=upload.diagnostic_session,
                role=DiagnosticEventRole.TOOL.value,
                content="Appliance image uploaded and queued for analysis.",
                tool_name="complete_image_upload",
                tool_payload={"image_upload_id": upload.id, "content_type": content_type},
            )
        )
        self._session.flush()
        self._vision_queue.enqueue(upload.id)
        return upload

    def list_session_uploads(self, *, session_id: int) -> list[ImageUpload]:
        self._get_diagnostic_session(session_id)
        statement = (
            select(ImageUpload)
            .where(ImageUpload.diagnostic_session_id == session_id)
            .order_by(ImageUpload.id.asc())
        )
        return list(self._session.scalars(statement).all())

    def _get_diagnostic_session(self, session_id: int) -> DiagnosticSession:
        statement = (
            select(DiagnosticSession)
            .where(DiagnosticSession.id == session_id)
            .options(
                selectinload(DiagnosticSession.events),
                selectinload(DiagnosticSession.image_uploads),
            )
        )
        diagnostic_session = self._session.scalars(statement).one_or_none()
        if diagnostic_session is None:
            raise DiagnosticSessionNotFoundError("Diagnostic session not found.")
        return diagnostic_session

    def _find_upload_by_token(self, token: str) -> ImageUpload:
        statement = (
            select(ImageUpload)
            .where(ImageUpload.token_hash == hash_upload_token(token))
            .options(selectinload(ImageUpload.diagnostic_session))
        )
        upload = self._session.scalars(statement).one_or_none()
        if upload is None:
            raise UploadTokenNotFoundError("Upload token not found.")
        return upload

    def _mark_expired_if_needed(self, upload: ImageUpload) -> None:
        if (
            _as_utc(upload.expires_at) <= datetime.now(UTC)
            and upload.status == ImageUploadStatus.PENDING_UPLOAD.value
        ):
            upload.status = ImageUploadStatus.EXPIRED.value
            self._session.flush()


class UploadTokenNotFoundError(LookupError):
    """Raised when an upload token is unknown."""


class UploadTokenExpiredError(ValueError):
    """Raised when an upload token is expired."""


class UploadValidationError(ValueError):
    """Raised when upload metadata violates security constraints."""


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise UploadValidationError("A valid email address is required.")
    return normalized


def redact_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not local or not domain:
        return "[redacted]"
    return f"{local[:1]}***@{domain}"


def sanitize_filename(filename: str) -> str:
    name = filename.strip().split("/")[-1].split("\\")[-1]
    if not name or len(name) > 255:
        raise UploadValidationError("A valid filename is required.")
    return name


def validate_upload_metadata(
    *,
    settings: Settings,
    filename: str,
    content_type: str,
    byte_size: int,
) -> None:
    sanitize_filename(filename)
    if content_type not in allowed_content_types(settings):
        raise UploadValidationError("Unsupported image content type.")
    if byte_size <= 0 or byte_size > settings.upload_max_bytes:
        raise UploadValidationError("Image size exceeds the upload limit.")


def allowed_content_types(settings: Settings) -> set[str]:
    return {
        content_type.strip()
        for content_type in settings.upload_allowed_content_types.split(",")
        if content_type.strip()
    }


def hash_upload_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_upload_url(settings: Settings, token: str) -> str:
    return f"{settings.upload_link_base_url.rstrip('/')}/{token}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
