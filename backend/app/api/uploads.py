"""Image upload and vision analysis HTTP routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import (
    get_db_session,
    get_upload_email_sender,
    get_upload_storage_client,
    get_vision_provider,
    get_vision_queue,
)
from app.exceptions import DiagnosticSessionNotFoundError
from app.schemas import (
    ImageUploadListResponse,
    ImageUploadRead,
    PresignedUploadResponse,
    UploadLinkRequest,
    UploadLinkResponse,
    UploadMetadataRequest,
)
from app.services.email import UploadEmailSender
from app.services.storage import UploadStorageClient
from app.services.uploads import (
    UploadService,
    UploadTokenExpiredError,
    UploadTokenNotFoundError,
    UploadValidationError,
)
from app.services.vision import (
    ImageUploadNotFoundError,
    VisionAnalysisProvider,
    VisionAnalysisService,
    VisionQueue,
)

router = APIRouter(tags=["uploads"])


@router.post(
    "/diagnostics/sessions/{session_id}/upload-link",
    response_model=UploadLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_upload_link(
    session_id: int,
    request: UploadLinkRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage_client: Annotated[UploadStorageClient, Depends(get_upload_storage_client)],
    email_sender: Annotated[UploadEmailSender, Depends(get_upload_email_sender)],
    vision_queue: Annotated[VisionQueue, Depends(get_vision_queue)],
) -> UploadLinkResponse:
    service = UploadService(session, settings, storage_client, email_sender, vision_queue)
    try:
        result = service.create_upload_link(session_id=session_id, email=request.email)
    except DiagnosticSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return UploadLinkResponse(
        id=result.upload.id,
        diagnostic_session_id=result.upload.diagnostic_session_id,
        upload_url=result.upload_url,
        expires_at=result.upload.expires_at,
        email_sent=result.email_sent,
        status=result.upload.status,
    )


@router.get("/uploads/{token}", response_model=ImageUploadRead)
def get_upload_token(
    token: str,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage_client: Annotated[UploadStorageClient, Depends(get_upload_storage_client)],
    email_sender: Annotated[UploadEmailSender, Depends(get_upload_email_sender)],
    vision_queue: Annotated[VisionQueue, Depends(get_vision_queue)],
) -> ImageUploadRead:
    service = UploadService(session, settings, storage_client, email_sender, vision_queue)
    try:
        upload = service.get_upload_by_token(token)
    except UploadTokenNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UploadTokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    return ImageUploadRead.model_validate(upload)


@router.post("/uploads/{token}/presigned-post", response_model=PresignedUploadResponse)
def create_presigned_upload(
    token: str,
    request: UploadMetadataRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage_client: Annotated[UploadStorageClient, Depends(get_upload_storage_client)],
    email_sender: Annotated[UploadEmailSender, Depends(get_upload_email_sender)],
    vision_queue: Annotated[VisionQueue, Depends(get_vision_queue)],
) -> PresignedUploadResponse:
    service = UploadService(session, settings, storage_client, email_sender, vision_queue)
    try:
        upload = service.get_upload_by_token(token)
        presigned_post = service.create_presigned_post(
            token=token,
            filename=request.filename,
            content_type=request.content_type,
            byte_size=request.byte_size,
        )
    except UploadTokenNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UploadTokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return PresignedUploadResponse(
        upload_id=upload.id,
        method="POST",
        url=presigned_post.url,
        fields=presigned_post.fields,
        max_byte_size=settings.upload_max_bytes,
        expires_at=upload.expires_at,
        storage_key=upload.storage_key,
    )


@router.post("/uploads/{token}/complete", response_model=ImageUploadRead)
def complete_upload(
    token: str,
    request: UploadMetadataRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage_client: Annotated[UploadStorageClient, Depends(get_upload_storage_client)],
    email_sender: Annotated[UploadEmailSender, Depends(get_upload_email_sender)],
    vision_queue: Annotated[VisionQueue, Depends(get_vision_queue)],
) -> ImageUploadRead:
    service = UploadService(session, settings, storage_client, email_sender, vision_queue)
    try:
        upload = service.complete_upload(
            token=token,
            filename=request.filename,
            content_type=request.content_type,
            byte_size=request.byte_size,
        )
    except UploadTokenNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UploadTokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    return ImageUploadRead.model_validate(upload)


@router.get(
    "/diagnostics/sessions/{session_id}/uploads",
    response_model=ImageUploadListResponse,
)
def list_session_uploads(
    session_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage_client: Annotated[UploadStorageClient, Depends(get_upload_storage_client)],
    email_sender: Annotated[UploadEmailSender, Depends(get_upload_email_sender)],
    vision_queue: Annotated[VisionQueue, Depends(get_vision_queue)],
) -> ImageUploadListResponse:
    service = UploadService(session, settings, storage_client, email_sender, vision_queue)
    try:
        uploads = service.list_session_uploads(session_id=session_id)
    except DiagnosticSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ImageUploadListResponse(
        uploads=[ImageUploadRead.model_validate(upload) for upload in uploads]
    )


@router.post("/diagnostics/uploads/{upload_id}/analysis", response_model=ImageUploadRead)
def analyze_upload(
    upload_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage_client: Annotated[UploadStorageClient, Depends(get_upload_storage_client)],
    vision_provider: Annotated[VisionAnalysisProvider, Depends(get_vision_provider)],
) -> ImageUploadRead:
    service = VisionAnalysisService(session, settings, storage_client, vision_provider)
    try:
        upload = service.process_upload(upload_id)
    except ImageUploadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ImageUploadRead.model_validate(upload)
