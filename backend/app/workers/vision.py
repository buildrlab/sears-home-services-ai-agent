"""Vision analysis worker entrypoint."""

from __future__ import annotations

import argparse
import json
import time

from app.config import Settings, get_settings
from app.database import session_scope
from app.services.vision import VisionAnalysisService


def process_message_body(body: str) -> int:
    payload = json.loads(body)
    if not isinstance(payload, dict) or "image_upload_id" not in payload:
        raise ValueError("Vision worker message must include image_upload_id.")
    upload_id = int(payload["image_upload_id"])
    settings = get_settings()
    with session_scope() as session:
        VisionAnalysisService(session, settings).process_upload(upload_id)
    return upload_id


def poll_sqs(
    settings: Settings,
    *,
    once: bool,
    wait_time_seconds: int,
    max_number_of_messages: int,
    visibility_timeout: int,
    idle_sleep_seconds: float = 1.0,
    client=None,
) -> int:
    if not settings.sqs_vision_queue_url:
        raise ValueError("SQS_VISION_QUEUE_URL is required for SQS polling.")
    sqs_client = client or _boto3_client(settings, "sqs")
    processed_count = 0

    while True:
        response = sqs_client.receive_message(
            QueueUrl=settings.sqs_vision_queue_url,
            MaxNumberOfMessages=max_number_of_messages,
            WaitTimeSeconds=wait_time_seconds,
            VisibilityTimeout=visibility_timeout,
        )
        messages = response.get("Messages", [])
        if not messages and once:
            return processed_count
        if not messages:
            time.sleep(idle_sleep_seconds)
            continue

        for message in messages:
            process_message_body(str(message["Body"]))
            sqs_client.delete_message(
                QueueUrl=settings.sqs_vision_queue_url,
                ReceiptHandle=str(message["ReceiptHandle"]),
            )
            processed_count += 1

        if once:
            return processed_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process one image upload vision job.")
    parser.add_argument("--message-body", help="SQS message body containing image_upload_id.")
    parser.add_argument("--upload-id", type=int, help="Local upload ID to process directly.")
    parser.add_argument("--poll-sqs", action="store_true", help="Poll SQS for vision jobs.")
    parser.add_argument("--once", action="store_true", help="Exit after one SQS receive batch.")
    parser.add_argument("--wait-time-seconds", type=int, default=20)
    parser.add_argument("--max-number-of-messages", type=int, default=5)
    parser.add_argument("--visibility-timeout", type=int, default=300)
    args = parser.parse_args(argv)

    if args.poll_sqs:
        settings = get_settings()
        processed_count = poll_sqs(
            settings,
            once=args.once,
            wait_time_seconds=args.wait_time_seconds,
            max_number_of_messages=args.max_number_of_messages,
            visibility_timeout=args.visibility_timeout,
        )
        print(json.dumps({"processed_messages": processed_count}))
        return 0
    if args.message_body:
        upload_id = process_message_body(args.message_body)
    elif args.upload_id:
        upload_id = args.upload_id
        settings = get_settings()
        with session_scope() as session:
            VisionAnalysisService(session, settings).process_upload(upload_id)
    else:
        parser.error("Either --message-body or --upload-id is required.")

    print(json.dumps({"processed_upload_id": upload_id}))
    return 0


def _boto3_client(settings: Settings, service_name: str):
    import boto3

    kwargs: dict[str, object] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client(service_name, **kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
