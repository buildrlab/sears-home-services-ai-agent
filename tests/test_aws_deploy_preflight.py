from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AWS_DIR = REPO_ROOT / "scripts" / "aws"


def _load_script_module(module_name: str, script_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, AWS_DIR / script_name)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load scripts/aws/{script_name}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


DEPLOY_PREFLIGHT = _load_script_module("aws_deploy_preflight_script", "deploy_preflight.py")


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args):
        key = tuple(args)
        self.calls.append(key)
        response = self.responses.get(key)
        if response is None:
            raise AssertionError(f"Unexpected command: {key}")
        return response


def result(args, returncode: int = 0, stdout: str = "", stderr: str = ""):
    return DEPLOY_PREFLIGHT.CommandResult(
        args=tuple(args),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class DeployPreflightTests(unittest.TestCase):
    def test_parse_name_table_handles_secret_and_variable_output(self) -> None:
        parsed = DEPLOY_PREFLIGHT.parse_name_table(
            "AWS_DEVOPS_ROLE_ARN\t2026-07-01\n"
            "SHS_WORKLOAD_ACCOUNT_ID\t710045722740\t2026-07-01\n"
        )

        self.assertEqual(parsed["AWS_DEVOPS_ROLE_ARN"], "2026-07-01")
        self.assertEqual(parsed["SHS_WORKLOAD_ACCOUNT_ID"], "710045722740")

    def test_required_github_secrets_are_reported(self) -> None:
        runner = FakeRunner(
            {
                (
                    "gh",
                    "secret",
                    "list",
                    "--repo",
                    "buildrlab/repo",
                    "--env",
                    "prod",
                ): result(
                    (
                        "gh",
                        "secret",
                        "list",
                        "--repo",
                        "buildrlab/repo",
                        "--env",
                        "prod",
                    ),
                    stdout="AWS_DEVOPS_ROLE_ARN\t2026-07-01\n",
                )
            }
        )

        checks = DEPLOY_PREFLIGHT.check_github_secrets(
            "buildrlab/repo",
            "prod",
            runner,
        )

        by_name = {check.name: check for check in checks}
        self.assertTrue(by_name["github_secret_AWS_DEVOPS_ROLE_ARN"].ok)
        self.assertFalse(by_name["github_secret_OPENAI_API_KEY"].ok)
        self.assertFalse(by_name["github_secret_TWILIO_AUTH_TOKEN"].ok)
        self.assertIn(
            (
                "gh",
                "secret",
                "list",
                "--repo",
                "buildrlab/repo",
                "--env",
                "prod",
            ),
            runner.calls,
        )

    def test_required_github_variables_validate_expected_values(self) -> None:
        runner = FakeRunner(
            {
                (
                    "gh",
                    "variable",
                    "list",
                    "--repo",
                    "buildrlab/repo",
                    "--env",
                    "prod",
                ): result(
                    (
                        "gh",
                        "variable",
                        "list",
                        "--repo",
                        "buildrlab/repo",
                        "--env",
                        "prod",
                    ),
                    stdout=(
                        "AWS_DEVOPS_ACCOUNT_ID\t123456789012\n"
                        "SHS_WORKLOAD_ACCOUNT_ID\t710045722740\n"
                        "SHS_DNS_ACCOUNT_ID\t202612164956\n"
                        "SHS_HOSTED_ZONE_ID\tZ05781442GINHB3A5IJXK\n"
                        "TF_STATE_BUCKET\twrong-bucket\n"
                    ),
                )
            }
        )

        checks = DEPLOY_PREFLIGHT.check_github_variables(
            "buildrlab/repo",
            "prod",
            runner,
        )

        by_name = {check.name: check for check in checks}
        self.assertTrue(by_name["github_variable_AWS_DEVOPS_ACCOUNT_ID"].ok)
        self.assertTrue(by_name["github_variable_SHS_WORKLOAD_ACCOUNT_ID"].ok)
        self.assertFalse(by_name["github_variable_TF_STATE_BUCKET"].ok)

    def test_branch_protection_reports_expected_policy(self) -> None:
        payload = {
            "required_status_checks": {
                "strict": True,
                "contexts": ["secret-scan"],
                "checks": [{"context": "dependency-audit"}],
            },
            "required_pull_request_reviews": {
                "required_approving_review_count": 0,
            },
            "required_conversation_resolution": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
            "enforce_admins": {"enabled": False},
        }
        runner = FakeRunner(
            {
                (
                    "gh",
                    "api",
                    "repos/buildrlab/repo/branches/dev/protection",
                ): result(
                    (
                        "gh",
                        "api",
                        "repos/buildrlab/repo/branches/dev/protection",
                    ),
                    stdout=json.dumps(payload),
                )
            }
        )

        checks = DEPLOY_PREFLIGHT.check_github_branch_protection(
            "buildrlab/repo",
            "dev",
            runner,
        )

        self.assertTrue(all(check.ok for check in checks))

    def test_branch_protection_reports_missing_required_checks(self) -> None:
        payload = {
            "required_status_checks": {
                "strict": False,
                "contexts": ["secret-scan"],
            },
            "required_pull_request_reviews": None,
            "required_conversation_resolution": {"enabled": False},
            "allow_force_pushes": {"enabled": True},
            "allow_deletions": {"enabled": True},
            "enforce_admins": {"enabled": True},
        }
        runner = FakeRunner(
            {
                (
                    "gh",
                    "api",
                    "repos/buildrlab/repo/branches/dev/protection",
                ): result(
                    (
                        "gh",
                        "api",
                        "repos/buildrlab/repo/branches/dev/protection",
                    ),
                    stdout=json.dumps(payload),
                )
            }
        )

        checks = DEPLOY_PREFLIGHT.check_github_branch_protection(
            "buildrlab/repo",
            "dev",
            runner,
        )

        by_name = {check.name: check for check in checks}
        self.assertFalse(by_name["github_branch_required_status_checks"].ok)
        self.assertIn(
            "dependency-audit",
            by_name["github_branch_required_status_checks"].detail,
        )
        self.assertFalse(by_name["github_branch_pull_request_required"].ok)
        self.assertFalse(by_name["github_branch_conversation_resolution"].ok)
        self.assertFalse(by_name["github_branch_blocks_force_pushes"].ok)
        self.assertFalse(by_name["github_branch_blocks_deletions"].ok)
        self.assertFalse(by_name["github_branch_admin_bypass"].ok)

    def test_run_preflight_checks_environment_and_branch_policy(self) -> None:
        branch_payload = {
            "required_status_checks": {
                "strict": True,
                "contexts": ["secret-scan", "dependency-audit"],
            },
            "required_pull_request_reviews": {
                "required_approving_review_count": 0,
            },
            "required_conversation_resolution": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
            "enforce_admins": {"enabled": False},
        }
        runner = FakeRunner(
            {
                ("gh", "auth", "status"): result(("gh", "auth", "status")),
                (
                    "gh",
                    "api",
                    "repos/buildrlab/repo/environments/prod",
                ): result(
                    (
                        "gh",
                        "api",
                        "repos/buildrlab/repo/environments/prod",
                    )
                ),
                (
                    "gh",
                    "secret",
                    "list",
                    "--repo",
                    "buildrlab/repo",
                    "--env",
                    "prod",
                ): result(
                    (
                        "gh",
                        "secret",
                        "list",
                        "--repo",
                        "buildrlab/repo",
                        "--env",
                        "prod",
                    ),
                    stdout=(
                        "AWS_DEVOPS_ROLE_ARN\t2026-07-01\n"
                        "OPENAI_API_KEY\t2026-07-01\n"
                        "TWILIO_AUTH_TOKEN\t2026-07-01\n"
                    ),
                ),
                (
                    "gh",
                    "variable",
                    "list",
                    "--repo",
                    "buildrlab/repo",
                    "--env",
                    "prod",
                ): result(
                    (
                        "gh",
                        "variable",
                        "list",
                        "--repo",
                        "buildrlab/repo",
                        "--env",
                        "prod",
                    ),
                    stdout=(
                        "AWS_DEVOPS_ACCOUNT_ID\t123456789012\n"
                        "SHS_WORKLOAD_ACCOUNT_ID\t710045722740\n"
                        "SHS_DNS_ACCOUNT_ID\t202612164956\n"
                        "SHS_HOSTED_ZONE_ID\tZ05781442GINHB3A5IJXK\n"
                        "TF_STATE_BUCKET\tbuildrlab-terraform-state\n"
                    ),
                ),
                (
                    "gh",
                    "api",
                    "repos/buildrlab/repo/branches/dev/protection",
                ): result(
                    (
                        "gh",
                        "api",
                        "repos/buildrlab/repo/branches/dev/protection",
                    ),
                    stdout=json.dumps(branch_payload),
                ),
                (
                    "aws",
                    "sts",
                    "get-caller-identity",
                    "--output",
                    "json",
                ): result(
                    ("aws", "sts", "get-caller-identity", "--output", "json"),
                    stdout='{"Account":"123456789012"}',
                ),
            }
        )

        checks = DEPLOY_PREFLIGHT.run_preflight(
            repository="buildrlab/repo",
            environment="prod",
            branch="dev",
            expected_aws_account_id="123456789012",
            runner=runner,
        )

        self.assertTrue(all(check.ok for check in checks))
        self.assertIn(
            (
                "gh",
                "secret",
                "list",
                "--repo",
                "buildrlab/repo",
                "--env",
                "prod",
            ),
            runner.calls,
        )
        self.assertIn(
            (
                "gh",
                "api",
                "repos/buildrlab/repo/branches/dev/protection",
            ),
            runner.calls,
        )

    def test_aws_identity_checks_expected_account(self) -> None:
        runner = FakeRunner(
            {
                (
                    "aws",
                    "sts",
                    "get-caller-identity",
                    "--output",
                    "json",
                ): result(
                    ("aws", "sts", "get-caller-identity", "--output", "json"),
                    stdout='{"Account":"123456789012"}',
                )
            }
        )

        ok_check = DEPLOY_PREFLIGHT.check_aws_identity(runner, "123456789012")
        bad_check = DEPLOY_PREFLIGHT.check_aws_identity(runner, "210987654321")

        self.assertTrue(ok_check.ok)
        self.assertFalse(bad_check.ok)


if __name__ == "__main__":
    unittest.main()
