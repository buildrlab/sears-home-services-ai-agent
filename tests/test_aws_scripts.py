from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AWS_DIR = REPO_ROOT / "scripts" / "aws"


def _load_script_module(module_name: str, script_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, AWS_DIR / script_name)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load scripts/aws/{script_name} for tests.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


REMOTE_SMOKE = _load_script_module("aws_remote_smoke_script", "remote_smoke.py")


class AwsRemoteSmokeTests(unittest.TestCase):
    def test_script_supports_help(self) -> None:
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(AWS_DIR / "remote_smoke.py"), "--help"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_normalize_base_url_rejects_relative_urls(self) -> None:
        with self.assertRaises(REMOTE_SMOKE.SmokeError):
            REMOTE_SMOKE.normalize_base_url("api.shs.buildrlab.com", label="test")

    def test_api_health_check_requires_expected_payload(self) -> None:
        def fetch(url: str, _timeout: float) -> Any:
            return REMOTE_SMOKE.FetchResult(
                url=url,
                status=200,
                body=(
                    b'{"status":"ok","service":"shs-ai-agent-backend",'
                    b'"environment":"prod"}'
                ),
                content_type="application/json",
            )

        result = REMOTE_SMOKE.check_api_health(
            "https://api.shs.buildrlab.com",
            1,
            fetch=fetch,
        )

        self.assertEqual(result["check"], "api_health")
        self.assertEqual(result["environment"], "prod")

    def test_api_health_check_fails_on_wrong_service(self) -> None:
        def fetch(url: str, _timeout: float) -> Any:
            return REMOTE_SMOKE.FetchResult(
                url=url,
                status=200,
                body=b'{"status":"ok","service":"wrong"}',
                content_type="application/json",
            )

        with self.assertRaises(REMOTE_SMOKE.SmokeError):
            REMOTE_SMOKE.check_api_health(
                "https://api.shs.buildrlab.com",
                1,
                fetch=fetch,
            )

    def test_frontend_checks_require_react_shell(self) -> None:
        html = (
            b"<!doctype html><title>Sears Home Services AI Agent</title>"
            b'<div id="root"></div>'
        )

        def fetch(url: str, _timeout: float) -> Any:
            return REMOTE_SMOKE.FetchResult(
                url=url,
                status=200,
                body=html,
                content_type="text/html",
            )

        shell = REMOTE_SMOKE.check_frontend_shell(
            "https://shs.buildrlab.com",
            1,
            fetch=fetch,
        )
        upload = REMOTE_SMOKE.check_frontend_upload_route(
            "https://shs.buildrlab.com",
            1,
            fetch=fetch,
        )

        self.assertEqual(shell["check"], "frontend_shell")
        self.assertEqual(upload["check"], "frontend_upload_route")


if __name__ == "__main__":
    unittest.main()
