"""Vision analysis provider, queue, and worker services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.models import DiagnosticEvent, DiagnosticEventRole, ImageUpload, ImageUploadStatus
from app.services.storage import UploadStorageClient, build_upload_storage_client


@dataclass(frozen=True)
class VisionAnalysisContext:
    image_url: str
    appliance_type: str | None
    symptoms: list[str]
    content_type: str | None


@dataclass(frozen=True)
class VisionAnalysisResult:
    summary: str
    observations: list[str]
    recommended_action: str

    def as_payload(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "observations": self.observations,
            "recommended_action": self.recommended_action,
        }


class VisionAnalysisProvider(Protocol):
    def analyze(self, context: VisionAnalysisContext) -> VisionAnalysisResult:
        """Analyze an appliance image."""


class VisionQueue(Protocol):
    def enqueue(self, upload_id: int) -> None:
        """Queue an image upload for asynchronous analysis."""


class NoopVisionQueue:
    def enqueue(self, upload_id: int) -> None:
        return None


class SqsVisionQueue:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = _boto3_client(settings, "sqs")

    def enqueue(self, upload_id: int) -> None:
        if not self._settings.sqs_vision_queue_url:
            return
        self._client.send_message(
            QueueUrl=self._settings.sqs_vision_queue_url,
            MessageBody=json.dumps({"image_upload_id": upload_id}),
        )


class DeterministicVisionAnalysisProvider:
    def analyze(self, context: VisionAnalysisContext) -> VisionAnalysisResult:
        appliance = context.appliance_type or "appliance"
        symptoms = ", ".join(context.symptoms) if context.symptoms else "reported issue"
        return VisionAnalysisResult(
            summary=(
                f"Image received for the {appliance}. Local deterministic analysis notes "
                f"the known symptoms as {symptoms} and recommends technician review."
            ),
            observations=[
                "Photo metadata is valid for the diagnostic session.",
                "No automated safety escalation was detected by the local analyzer.",
            ],
            recommended_action="schedule_technician",
        )


class OpenAIVisionAnalysisProvider:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
        self._settings = settings
        self._client = client

    def analyze(self, context: VisionAnalysisContext) -> VisionAnalysisResult:
        response = self._client.responses.create(
            model=self._settings.openai_vision_model,
            instructions=(
                "You are a Sears Home Services appliance diagnostic assistant. "
                "Inspect the image for visible appliance condition clues. Do not give "
                "unsafe repair instructions. Recommend technician scheduling when the "
                "image does not clearly rule out service."
            ),
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Analyze this appliance image for a diagnostic session. "
                                f"Known appliance: {context.appliance_type or 'unknown'}. "
                                f"Known symptoms: {', '.join(context.symptoms) or 'unknown'}."
                            ),
                        },
                        {"type": "input_image", "image_url": context.image_url},
                    ],
                }
            ],
            text={"verbosity": self._settings.openai_verbosity},
        )
        summary = getattr(response, "output_text", "") or (
            "Image analysis completed; technician review is recommended."
        )
        return VisionAnalysisResult(
            summary=summary,
            observations=[summary],
            recommended_action="schedule_technician",
        )


class VisionAnalysisService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        storage_client: UploadStorageClient | None = None,
        provider: VisionAnalysisProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage_client = storage_client or build_upload_storage_client(settings)
        self._provider = provider or build_vision_analysis_provider(settings)

    def process_upload(self, upload_id: int) -> ImageUpload:
        upload = self._get_upload(upload_id)
        upload.status = ImageUploadStatus.ANALYSIS_PENDING.value
        upload.analysis_started_at = datetime.now(UTC)
        self._session.flush()

        try:
            image_url = self._storage_client.create_presigned_get_url(
                bucket=upload.storage_bucket,
                key=upload.storage_key,
                expires_seconds=self._settings.vision_presigned_get_expires_seconds,
            )
            diagnostic_session = upload.diagnostic_session
            result = self._provider.analyze(
                VisionAnalysisContext(
                    image_url=image_url,
                    appliance_type=diagnostic_session.appliance_type,
                    symptoms=diagnostic_session.symptoms,
                    content_type=upload.content_type,
                )
            )
        except Exception as exc:
            upload.status = ImageUploadStatus.FAILED.value
            upload.failure_reason = str(exc)
            self._session.add(
                DiagnosticEvent(
                    session=upload.diagnostic_session,
                    role=DiagnosticEventRole.TOOL.value,
                    content=f"Image analysis failed: {exc}",
                    tool_name="analyze_image_failed",
                    tool_payload={"image_upload_id": upload.id, "error": str(exc)},
                )
            )
            self._session.flush()
            return upload

        upload.status = ImageUploadStatus.ANALYZED.value
        upload.analyzed_at = datetime.now(UTC)
        upload.analysis_summary = result.summary
        upload.analysis_result = result.as_payload()
        upload.failure_reason = None
        self._session.add(
            DiagnosticEvent(
                session=upload.diagnostic_session,
                role=DiagnosticEventRole.TOOL.value,
                content=f"Image analysis completed: {result.summary}",
                tool_name="analyze_image",
                tool_payload={"image_upload_id": upload.id, **result.as_payload()},
            )
        )
        self._session.flush()
        return upload

    def _get_upload(self, upload_id: int) -> ImageUpload:
        statement = (
            select(ImageUpload)
            .where(ImageUpload.id == upload_id)
            .options(selectinload(ImageUpload.diagnostic_session))
        )
        upload = self._session.scalars(statement).one_or_none()
        if upload is None:
            raise ImageUploadNotFoundError("Image upload not found.")
        return upload


class ImageUploadNotFoundError(LookupError):
    """Raised when an image upload does not exist."""


def build_vision_analysis_provider(settings: Settings) -> VisionAnalysisProvider:
    if settings.openai_api_key:
        return OpenAIVisionAnalysisProvider(settings)
    return DeterministicVisionAnalysisProvider()


def build_vision_queue(settings: Settings) -> VisionQueue:
    if settings.sqs_vision_queue_url:
        return SqsVisionQueue(settings)
    return NoopVisionQueue()


def _boto3_client(settings: Settings, service_name: str):
    import boto3

    kwargs: dict[str, object] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client(service_name, **kwargs)
