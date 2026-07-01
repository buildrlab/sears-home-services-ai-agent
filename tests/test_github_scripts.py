from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
GITHUB_DIR = REPO_ROOT / "scripts" / "github"


def _load_script_module(module_name: str, script_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, GITHUB_DIR / script_name)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load scripts/github/{script_name}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


CONFIGURE_DEPLOY = _load_script_module(
    "github_configure_deploy_script",
    "configure_deploy.py",
)
CONFIGURE_BRANCH_PROTECTION = _load_script_module(
    "github_configure_branch_protection_script",
    "configure_branch_protection.py",
)


class ConfigureDeployTests(unittest.TestCase):
    def test_build_plan_creates_environment_and_variables(self) -> None:
        plan = CONFIGURE_DEPLOY.build_plan(
            repository="buildrlab/repo",
            environment_name="prod",
            aws_devops_account_id="123456789012",
            include_secrets=False,
            environ={},
        )

        self.assertTrue(plan.ok)
        commands = [command.args for command in plan.commands]
        self.assertIn(
            (
                "gh",
                "api",
                "--method",
                "PUT",
                "repos/buildrlab/repo/environments/prod",
            ),
            commands,
        )
        self.assertIn(
            (
                "gh",
                "variable",
                "set",
                "TF_STATE_BUCKET",
                "--repo",
                "buildrlab/repo",
                "--env",
                "prod",
                "--body",
                "buildrlab-terraform-state",
            ),
            commands,
        )

    def test_build_plan_requires_devops_account_id(self) -> None:
        plan = CONFIGURE_DEPLOY.build_plan(
            repository="buildrlab/repo",
            environment_name="prod",
            aws_devops_account_id=None,
            include_secrets=False,
            environ={},
        )

        self.assertFalse(plan.ok)
        self.assertIn("AWS_DEVOPS_ACCOUNT_ID", plan.missing)

    def test_build_plan_redacts_secret_display(self) -> None:
        plan = CONFIGURE_DEPLOY.build_plan(
            repository="buildrlab/repo",
            environment_name="prod",
            aws_devops_account_id="123456789012",
            include_secrets=True,
            environ={
                "AWS_DEVOPS_ROLE_ARN": "arn:secret",
                "OPENAI_API_KEY": "sk-secret",
                "TWILIO_AUTH_TOKEN": "twilio-secret",
            },
        )

        secret_commands = [
            command for command in plan.commands if command.stdin_value is not None
        ]
        self.assertEqual(len(secret_commands), 3)
        for command in secret_commands:
            self.assertNotIn("arn:secret", command.display())
            self.assertNotIn("sk-secret", command.display())
            self.assertNotIn("twilio-secret", command.display())
            self.assertIn("<stdin:redacted>", command.display())
            self.assertNotIn("arn:secret", command.args)
            self.assertNotIn("sk-secret", command.args)
            self.assertNotIn("twilio-secret", command.args)

    def test_apply_plan_runs_secret_through_stdin(self) -> None:
        command = CONFIGURE_DEPLOY.PlannedCommand(
            label="set_secret",
            args=("gh", "secret", "set", "TOKEN"),
            stdin_value="value",
        )
        plan = CONFIGURE_DEPLOY.ConfigurationPlan(commands=[command], missing=[])
        calls: list[tuple[tuple[str, ...], str | None]] = []

        def runner(args, stdin):
            calls.append((tuple(args), stdin))
            return 0

        result = CONFIGURE_DEPLOY.apply_plan(plan, runner=runner)

        self.assertEqual(result, 0)
        self.assertEqual(calls, [(("gh", "secret", "set", "TOKEN"), "value")])


class ConfigureBranchProtectionTests(unittest.TestCase):
    def test_build_plan_uses_conservative_dev_protection(self) -> None:
        plan = CONFIGURE_BRANCH_PROTECTION.build_plan(
            repository="buildrlab/repo",
            branch="dev",
            required_checks=("secret-scan", "dependency-audit", "secret-scan"),
        )

        self.assertEqual(plan.repository, "buildrlab/repo")
        self.assertEqual(plan.branch, "dev")
        self.assertEqual(plan.required_checks, ("secret-scan", "dependency-audit"))
        self.assertEqual(
            plan.command,
            (
                "gh",
                "api",
                "--method",
                "PUT",
                "repos/buildrlab/repo/branches/dev/protection",
                "--input",
                "-",
            ),
        )
        self.assertEqual(
            plan.payload["required_status_checks"],
            {
                "strict": True,
                "contexts": ["secret-scan", "dependency-audit"],
            },
        )
        self.assertFalse(plan.payload["enforce_admins"])
        self.assertTrue(plan.payload["required_conversation_resolution"])
        self.assertFalse(plan.payload["allow_force_pushes"])
        self.assertFalse(plan.payload["allow_deletions"])
        self.assertEqual(
            plan.payload["required_pull_request_reviews"][
                "required_approving_review_count"
            ],
            0,
        )

    def test_build_plan_can_disable_required_checks(self) -> None:
        plan = CONFIGURE_BRANCH_PROTECTION.build_plan(
            repository="buildrlab/repo",
            branch="dev",
            required_checks=(),
        )

        self.assertEqual(plan.required_checks, ())
        self.assertIsNone(plan.payload["required_status_checks"])

    def test_apply_plan_sends_json_payload_to_stdin(self) -> None:
        plan = CONFIGURE_BRANCH_PROTECTION.build_plan(
            repository="buildrlab/repo",
            branch="dev",
            required_checks=("secret-scan",),
        )
        calls: list[tuple[tuple[str, ...], str]] = []

        def runner(args, stdin):
            calls.append((tuple(args), stdin))
            return 0

        result = CONFIGURE_BRANCH_PROTECTION.apply_plan(plan, runner=runner)

        self.assertEqual(result, 0)
        self.assertEqual(calls[0][0], plan.command)
        self.assertIn('"contexts": ["secret-scan"]', calls[0][1])


if __name__ == "__main__":
    unittest.main()
