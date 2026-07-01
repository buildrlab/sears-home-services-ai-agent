"""Upload-link email delivery."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from html import escape
from typing import Protocol

from app.config import Settings


@dataclass(frozen=True)
class UploadEmail:
    subject: str
    text_body: str
    html_body: str


class UploadEmailSender(Protocol):
    def send_upload_link(self, *, to_email: str, upload_url: str, expires_at: datetime) -> None:
        """Send a secure upload link to the caller."""


class SmtpUploadEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send_upload_link(self, *, to_email: str, upload_url: str, expires_at: datetime) -> None:
        rendered = render_upload_email(upload_url=upload_url, expires_at=expires_at)
        message = EmailMessage()
        message["Subject"] = rendered.subject
        message["From"] = self._settings.email_from_address
        message["To"] = to_email
        message.set_content(rendered.text_body)
        message.add_alternative(rendered.html_body, subtype="html")
        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=10) as smtp:
            smtp.send_message(message)


class SesUploadEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = _boto3_client(settings, "sesv2")

    def send_upload_link(self, *, to_email: str, upload_url: str, expires_at: datetime) -> None:
        rendered = render_upload_email(upload_url=upload_url, expires_at=expires_at)
        self._client.send_email(
            FromEmailAddress=self._settings.email_from_address,
            Destination={"ToAddresses": [to_email]},
            Content={
                "Simple": {
                    "Subject": {"Data": rendered.subject},
                    "Body": {
                        "Text": {"Data": rendered.text_body},
                        "Html": {"Data": rendered.html_body},
                    },
                }
            },
        )


def build_upload_email_sender(settings: Settings) -> UploadEmailSender:
    if settings.email_delivery_mode == "ses":
        return SesUploadEmailSender(settings)
    return SmtpUploadEmailSender(settings)


def render_upload_email(*, upload_url: str, expires_at: datetime) -> UploadEmail:
    expires_text = expires_at.isoformat()
    escaped_upload_url = escape(upload_url, quote=True)
    escaped_expires_text = escape(expires_text)
    subject = "Sears Home Services appliance photo upload"
    text_body = (
        "Upload appliance photos for your Sears Home Services diagnostic session:\n\n"
        f"{upload_url}\n\n"
        f"This secure link expires at {expires_text}."
    )
    html_body = (
        "<p>Upload appliance photos for your Sears Home Services diagnostic session.</p>"
        f'<p><a href="{escaped_upload_url}">Open secure upload link</a></p>'
        f"<p>This secure link expires at {escaped_expires_text}.</p>"
    )
    return UploadEmail(subject=subject, text_body=text_body, html_body=html_body)


def _boto3_client(settings: Settings, service_name: str):
    import boto3

    kwargs: dict[str, object] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client(service_name, **kwargs)
