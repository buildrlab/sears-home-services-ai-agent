from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEWER_DIR = REPO_ROOT / "scripts" / "reviewer"


def _load_script_module(module_name: str, script_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, REVIEWER_DIR / script_name)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load scripts/reviewer/{script_name}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


LOCAL_SMOKE = _load_script_module("reviewer_local_smoke_script", "local_smoke.py")


class FakeReviewerClient:
    def __init__(self) -> None:
        self.object_uploaded = False
        self.appointment_attempts = 0

    def get_json(self, path: str) -> dict[str, Any]:
        if path == "/healthz":
            return {
                "status": "ok",
                "service": "shs-ai-agent-backend",
                "environment": "test",
            }
        if path.startswith("/scheduling/matches"):
            return {
                "matches": [
                    {
                        "id": 1,
                        "name": "Avery Johnson",
                        "email": "avery.johnson@example.test",
                        "specialties": ["refrigerator"],
                        "service_areas": ["75201"],
                        "availability": [
                            {
                                "day_of_week": 0,
                                "start_time": "08:00:00",
                                "end_time": "12:00:00",
                                "capacity": 1,
                            }
                        ],
                    }
                ]
            }
        if path == "/uploads/test-token":
            return {"status": "pending_upload"}
        if path == "/diagnostics/sessions/123":
            return {"events": [{"tool_name": "analyze_image"}]}
        raise AssertionError(f"Unexpected GET {path}")

    def post_json(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if path == "/diagnostics/sessions":
            return {"id": 123}
        if path == "/diagnostics/sessions/123/turn":
            message = payload["message"] if payload else ""
            if "75201" in message:
                return {
                    "session": {
                        "appliance_type": "refrigerator",
                        "zip_code": "75201",
                        "symptoms": ["not cooling", "leaking"],
                        "status": "ready_to_schedule",
                    },
                    "tool_calls": [{"name": "find_technician_matches", "arguments": {}}],
                }
            return {
                "session": {
                    "appliance_type": "refrigerator",
                    "zip_code": None,
                    "symptoms": ["not cooling", "leaking"],
                    "status": "collecting",
                },
                "tool_calls": [],
            }
        if path == "/appointments/holds":
            self.appointment_attempts += 1
            return {"id": 456}
        if path == "/appointments/456/book":
            return {"status": "booked", "confirmation_code": "SHS-TEST"}
        if path == "/diagnostics/sessions/123/upload-link":
            return {
                "id": 789,
                "upload_url": "http://127.0.0.1:5173/uploads/test-token",
            }
        if path == "/uploads/test-token/presigned-post":
            return {
                "url": "http://127.0.0.1:9000/shs-ai-agent-uploads-local",
                "fields": {"key": "uploads/test.png"},
                "storage_key": "uploads/test.png",
            }
        if path == "/uploads/test-token/complete":
            return {"id": 789, "status": "analysis_pending"}
        if path == "/diagnostics/uploads/789/analysis":
            return {
                "status": "analyzed",
                "analysis_summary": "Image received for the refrigerator.",
            }
        raise AssertionError(f"Unexpected POST {path}")

    def post_form(self, path: str, payload: dict[str, str]) -> str:
        if path in {"/twilio/voice/incoming", "/twilio/voice/gather"}:
            return "<Response><Gather></Gather></Response>"
        raise AssertionError(f"Unexpected form POST {path}")

    def get_text_url(self, url: str) -> str:
        if url.startswith("http://127.0.0.1:5173"):
            return '<!doctype html><div id="root"></div>'
        raise AssertionError(f"Unexpected URL GET {url}")

    def post_multipart_url(
        self,
        url: str,
        fields: dict[str, str],
        *,
        filename: str,
        content_type: str,
        body: bytes,
    ) -> None:
        self.object_uploaded = True
        self.multipart_url = url
        self.multipart_fields = fields
        self.multipart_filename = filename
        self.multipart_content_type = content_type
        self.multipart_body = body


class ReviewerLocalSmokeTests(unittest.TestCase):
    def test_extract_upload_token(self) -> None:
        self.assertEqual(
            LOCAL_SMOKE.extract_upload_token("https://shs.example/uploads/token-123"),
            "token-123",
        )

    def test_next_weekday_handles_same_day(self) -> None:
        monday = date(2026, 7, 6)
        self.assertEqual(LOCAL_SMOKE.next_weekday(monday, 0), monday)
        self.assertEqual(LOCAL_SMOKE.next_weekday(monday, 2), date(2026, 7, 8))

    def test_candidate_starts_fit_inside_window(self) -> None:
        candidates = LOCAL_SMOKE.candidate_starts(
            [
                {
                    "day_of_week": 0,
                    "start_time": "08:00:00",
                    "end_time": "09:00:00",
                }
            ],
            duration_minutes=30,
            attempts_per_window=10,
        )

        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertEqual(candidate.weekday(), 0)
            self.assertGreaterEqual(candidate.hour * 60 + candidate.minute, 8 * 60)
            self.assertLessEqual(candidate.hour * 60 + candidate.minute + 30, 9 * 60)

    def test_build_multipart_body_contains_fields_and_file(self) -> None:
        body, content_type = LOCAL_SMOKE.build_multipart_body(
            {"key": "uploads/test.png"},
            filename="test.png",
            content_type="image/png",
            body=b"png",
        )

        self.assertIn("multipart/form-data; boundary=", content_type)
        self.assertIn(b'name="key"', body)
        self.assertIn(b"uploads/test.png", body)
        self.assertIn(b'filename="test.png"', body)
        self.assertIn(b"png", body)

    def test_run_reviewer_smoke_exercises_all_local_tiers(self) -> None:
        client = FakeReviewerClient()

        checks = LOCAL_SMOKE.run_reviewer_smoke(
            client,
            frontend_base_url="http://127.0.0.1:5173",
            upload_object=True,
        )

        check_names = {check.name for check in checks}
        self.assertIn("tier1_diagnostic_flow", check_names)
        self.assertIn("tier2_appointment_booked", check_names)
        self.assertIn("twilio_gather_fallback", check_names)
        self.assertIn("tier3_image_analysis", check_names)
        self.assertIn("frontend_shell", check_names)
        self.assertTrue(client.object_uploaded)


if __name__ == "__main__":
    unittest.main()
