"""Vision analysis worker entrypoint."""

from __future__ import annotations

import argparse
import json

from app.config import get_settings
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process one image upload vision job.")
    parser.add_argument("--message-body", help="SQS message body containing image_upload_id.")
    parser.add_argument("--upload-id", type=int, help="Local upload ID to process directly.")
    args = parser.parse_args(argv)

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


if __name__ == "__main__":
    raise SystemExit(main())
