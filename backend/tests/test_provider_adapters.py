from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.config import Settings
from app.services import email, storage, vision
from app.services.email import SesUploadEmailSender, SmtpUploadEmailSender
from app.services.storage import S3UploadStorageClient
from app.services.vision import (
    DeterministicVisionAnalysisProvider,
    OpenAIVisionAnalysisProvider,
    SqsVisionQueue,
    VisionAnalysisContext,
)


class FakeSesClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    def send_email(self, **kwargs) -> None:
        self.sent.append(kwargs)


class FakeSmtpConnection:
    sent_messages: list[object] = []

    def __init__(self, host: str, port: int, *, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def send_message(self, message) -> None:
        self.sent_messages.append(message)


class FakeS3Client:
    def __init__(self) -> None:
        self.post_kwargs: dict[str, object] | None = None
        self.url_kwargs: dict[str, object] | None = None

    def generate_presigned_post(self, **kwargs) -> dict[str, object]:
        self.post_kwargs = kwargs
        return {
            "url": "https://s3.example.test/upload",
            "fields": {"key": kwargs["Key"], "policy": "policy"},
        }

    def generate_presigned_url(self, operation_name: str, **kwargs) -> str:
        self.url_kwargs = {"operation_name": operation_name, **kwargs}
        return "https://s3.example.test/object"


class FakeSqsClient:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_message(self, **kwargs) -> None:
        self.messages.append(kwargs)


class FakeResponses:
    def __init__(self, output_text: str = "") -> None:
        self.output_text = output_text
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.output_text)


class FakeOpenAIClient:
    def __init__(self, output_text: str = "") -> None:
        self.responses = FakeResponses(output_text=output_text)


def test_ses_upload_email_sender_uses_ses_simple_email_payload(monkeypatch) -> None:
    fake_client = FakeSesClient()
    monkeypatch.setattr(email, "_boto3_client", lambda settings, service_name: fake_client)
    settings = Settings(
        environment="test",
        email_delivery_mode="ses",
        email_from_address="noreply@example.test",
    )

    sender = SesUploadEmailSender(settings)
    sender.send_upload_link(
        to_email="caller@example.test",
        upload_url="https://shs.example.test/uploads/token",
        expires_at=datetime(2026, 7, 1, 12, 30, tzinfo=UTC),
    )

    payload = fake_client.sent[0]
    assert payload["FromEmailAddress"] == "noreply@example.test"
    assert payload["Destination"] == {"ToAddresses": ["caller@example.test"]}
    simple = payload["Content"]["Simple"]  # type: ignore[index]
    assert simple["Subject"]["Data"] == "Sears Home Services appliance photo upload"
    assert "https://shs.example.test/uploads/token" in simple["Body"]["Text"]["Data"]
    assert "Open secure upload link" in simple["Body"]["Html"]["Data"]


def test_smtp_upload_email_sender_builds_multipart_message(monkeypatch) -> None:
    FakeSmtpConnection.sent_messages = []
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSmtpConnection)
    settings = Settings(
        environment="test",
        smtp_host="mailpit",
        smtp_port=1025,
        email_from_address="noreply@example.test",
    )

    SmtpUploadEmailSender(settings).send_upload_link(
        to_email="caller@example.test",
        upload_url="https://shs.example.test/uploads/token",
        expires_at=datetime(2026, 7, 1, 12, 30, tzinfo=UTC),
    )

    message = FakeSmtpConnection.sent_messages[0]
    assert message["From"] == "noreply@example.test"
    assert message["To"] == "caller@example.test"
    assert message["Subject"] == "Sears Home Services appliance photo upload"
    assert message.is_multipart()


def test_build_upload_email_sender_selects_configured_delivery_mode(monkeypatch) -> None:
    monkeypatch.setattr(email, "_boto3_client", lambda settings, service_name: FakeSesClient())

    ses_sender = email.build_upload_email_sender(
        Settings(environment="test", email_delivery_mode="ses")
    )
    smtp_sender = email.build_upload_email_sender(
        Settings(environment="test", email_delivery_mode="smtp")
    )

    assert isinstance(ses_sender, SesUploadEmailSender)
    assert isinstance(smtp_sender, SmtpUploadEmailSender)


def test_s3_upload_storage_client_creates_limited_post_and_get_url(monkeypatch) -> None:
    fake_client = FakeS3Client()
    monkeypatch.setattr(storage, "_s3_client", lambda settings: fake_client)
    client = S3UploadStorageClient(Settings(environment="test"))

    post = client.create_presigned_post(
        bucket="uploads",
        key="diagnostic-sessions/1/uploads/photo.png",
        content_type="image/png",
        max_bytes=1024,
        expires_seconds=300,
    )
    get_url = client.create_presigned_get_url(
        bucket="uploads",
        key="diagnostic-sessions/1/uploads/photo.png",
        expires_seconds=60,
    )

    assert post.url == "https://s3.example.test/upload"
    assert post.fields["key"] == "diagnostic-sessions/1/uploads/photo.png"
    assert fake_client.post_kwargs["Conditions"] == [
        {"Content-Type": "image/png"},
        ["content-length-range", 1, 1024],
    ]
    assert get_url == "https://s3.example.test/object"
    assert fake_client.url_kwargs == {
        "operation_name": "get_object",
        "Params": {"Bucket": "uploads", "Key": "diagnostic-sessions/1/uploads/photo.png"},
        "ExpiresIn": 60,
    }


def test_build_upload_storage_client_returns_s3_client(monkeypatch) -> None:
    monkeypatch.setattr(storage, "_s3_client", lambda settings: FakeS3Client())

    client = storage.build_upload_storage_client(Settings(environment="test"))

    assert isinstance(client, S3UploadStorageClient)


def test_sqs_vision_queue_sends_upload_id_message(monkeypatch) -> None:
    fake_client = FakeSqsClient()
    monkeypatch.setattr(vision, "_boto3_client", lambda settings, service_name: fake_client)
    queue = SqsVisionQueue(
        Settings(environment="test", sqs_vision_queue_url="https://sqs.example.test/queue")
    )

    queue.enqueue(91)

    assert fake_client.messages == [
        {
            "QueueUrl": "https://sqs.example.test/queue",
            "MessageBody": '{"image_upload_id": 91}',
        }
    ]


def test_sqs_vision_queue_noops_without_queue_url(monkeypatch) -> None:
    fake_client = FakeSqsClient()
    monkeypatch.setattr(vision, "_boto3_client", lambda settings, service_name: fake_client)

    SqsVisionQueue(Settings(environment="test")).enqueue(91)

    assert fake_client.messages == []


def test_vision_factory_selects_openai_or_deterministic_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        vision,
        "OpenAIVisionAnalysisProvider",
        lambda settings: "openai-provider",
    )

    assert (
        vision.build_vision_analysis_provider(Settings(openai_api_key="test"))
        == "openai-provider"
    )
    assert isinstance(
        vision.build_vision_analysis_provider(Settings(openai_api_key=None)),
        DeterministicVisionAnalysisProvider,
    )


def test_openai_vision_provider_uses_image_contract_and_fallback_summary() -> None:
    client = FakeOpenAIClient(output_text="")
    provider = OpenAIVisionAnalysisProvider(
        Settings(openai_api_key="test", openai_vision_model="gpt-vision-test"),
        client=client,
    )

    result = provider.analyze(
        VisionAnalysisContext(
            image_url="https://s3.example.test/object",
            appliance_type="refrigerator",
            symptoms=["leaking"],
            content_type="image/png",
        )
    )

    assert client.responses.kwargs["model"] == "gpt-vision-test"
    prompt_content = client.responses.kwargs["input"][0]["content"]  # type: ignore[index]
    assert prompt_content[0]["type"] == "input_text"
    assert "Known appliance: refrigerator" in prompt_content[0]["text"]
    assert prompt_content[1] == {
        "type": "input_image",
        "image_url": "https://s3.example.test/object",
    }
    assert result.summary == "Image analysis completed; technician review is recommended."
    assert result.recommended_action == "schedule_technician"


def test_deterministic_vision_provider_handles_unknown_context() -> None:
    result = DeterministicVisionAnalysisProvider().analyze(
        VisionAnalysisContext(
            image_url="https://s3.example.test/object",
            appliance_type=None,
            symptoms=[],
            content_type=None,
        )
    )

    assert "the appliance" in result.summary
    assert "reported issue" in result.summary
    assert result.recommended_action == "schedule_technician"
