"""S3-compatible upload storage helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import Settings


@dataclass(frozen=True)
class PresignedPost:
    url: str
    fields: dict[str, str]


class UploadStorageClient(Protocol):
    def create_presigned_post(
        self,
        *,
        bucket: str,
        key: str,
        content_type: str,
        max_bytes: int,
        expires_seconds: int,
    ) -> PresignedPost:
        """Create a browser-uploadable presigned POST."""

    def create_presigned_get_url(
        self,
        *,
        bucket: str,
        key: str,
        expires_seconds: int,
    ) -> str:
        """Create a short-lived object URL for the vision provider."""


class S3UploadStorageClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = _s3_client(settings)

    def create_presigned_post(
        self,
        *,
        bucket: str,
        key: str,
        content_type: str,
        max_bytes: int,
        expires_seconds: int,
    ) -> PresignedPost:
        response = self._client.generate_presigned_post(
            Bucket=bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=expires_seconds,
        )
        return PresignedPost(
            url=str(response["url"]),
            fields={str(key): str(value) for key, value in response["fields"].items()},
        )

    def create_presigned_get_url(
        self,
        *,
        bucket: str,
        key: str,
        expires_seconds: int,
    ) -> str:
        return str(
            self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_seconds,
            )
        )


def build_upload_storage_client(settings: Settings) -> UploadStorageClient:
    return S3UploadStorageClient(settings)


def _s3_client(settings: Settings):
    import boto3
    from botocore.config import Config

    kwargs: dict[str, object] = {
        "region_name": settings.aws_region,
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("s3", **kwargs)
