#!/usr/bin/env python3
"""Read-only deployment readiness checks for the SHS AWS deploy workflow."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

DEFAULT_REPOSITORY = "buildrlab/sears-home-services-ai-agent"
DEFAULT_ENVIRONMENT = "prod"

REQUIRED_SECRETS = (
    "AWS_DEVOPS_ROLE_ARN",
    "OPENAI_API_KEY",
    "TWILIO_AUTH_TOKEN",
)

REQUIRED_VARIABLES = {
    "SHS_WORKLOAD_ACCOUNT_ID": "710045722740",
    "SHS_DNS_ACCOUNT_ID": "202612164956",
    "SHS_HOSTED_ZONE_ID": "Z05781442GINHB3A5IJXK",
    "TF_STATE_BUCKET": "buildrlab-terraform-state",
}

REQUIRED_VARIABLE_NAMES_WITHOUT_FIXED_VALUE = ("AWS_DEVOPS_ACCOUNT_ID",)


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


class Runner(Protocol):
    def __call__(self, args: Sequence[str]) -> CommandResult:
        """Run a command and return a captured result."""


def run_command(args: Sequence[str]) -> CommandResult:
    completed = subprocess.run(  # noqa: S603
        list(args),
        capture_output=True,
        check=False,
        text=True,
    )
    return CommandResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def parse_name_table(output: str) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if not parts:
            continue
        values[parts[0]] = parts[1] if len(parts) > 1 else None
    return values


def check_binary(name: str) -> Check:
    path = shutil.which(name)
    return Check(name=f"{name}_installed", ok=path is not None, detail=path or "not found")


def check_gh_auth(runner: Runner) -> Check:
    result = runner(("gh", "auth", "status"))
    if result.returncode == 0:
        return Check("github_cli_auth", True, "authenticated")
    detail = (result.stderr or result.stdout).strip() or "gh auth status failed"
    return Check("github_cli_auth", False, detail)


def check_github_environment(repository: str, environment: str, runner: Runner) -> Check:
    result = runner(("gh", "api", f"repos/{repository}/environments/{environment}"))
    if result.returncode == 0:
        return Check("github_environment", True, environment)
    detail = (result.stderr or result.stdout).strip() or f"{environment} not found"
    return Check("github_environment", False, detail)


def check_github_secrets(repository: str, runner: Runner) -> list[Check]:
    result = runner(("gh", "secret", "list", "--repo", repository))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "gh secret list failed"
        return [Check("github_secrets", False, detail)]
    existing = parse_name_table(result.stdout)
    return [
        Check(
            name=f"github_secret_{secret_name}",
            ok=secret_name in existing,
            detail="present" if secret_name in existing else "missing",
        )
        for secret_name in REQUIRED_SECRETS
    ]


def check_github_variables(repository: str, runner: Runner) -> list[Check]:
    result = runner(("gh", "variable", "list", "--repo", repository))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "gh variable list failed"
        return [Check("github_variables", False, detail)]
    existing = parse_name_table(result.stdout)
    checks: list[Check] = []
    for variable_name in REQUIRED_VARIABLE_NAMES_WITHOUT_FIXED_VALUE:
        checks.append(
            Check(
                name=f"github_variable_{variable_name}",
                ok=variable_name in existing,
                detail="present" if variable_name in existing else "missing",
            )
        )
    for variable_name, expected_value in REQUIRED_VARIABLES.items():
        actual = existing.get(variable_name)
        checks.append(
            Check(
                name=f"github_variable_{variable_name}",
                ok=actual == expected_value,
                detail=f"expected {expected_value}, got {actual}" if actual else "missing",
            )
        )
    return checks


def check_aws_identity(runner: Runner, expected_account_id: str | None) -> Check:
    result = runner(("aws", "sts", "get-caller-identity", "--output", "json"))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "aws sts get-caller-identity failed"
        return Check("aws_identity", False, detail)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return Check("aws_identity", False, f"invalid JSON: {exc}")
    account_id = str(payload.get("Account", ""))
    if expected_account_id and account_id != expected_account_id:
        return Check(
            "aws_identity",
            False,
            f"expected account {expected_account_id}, got {account_id}",
        )
    return Check("aws_identity", True, account_id)


def run_preflight(
    *,
    repository: str,
    environment: str,
    expected_aws_account_id: str | None,
    runner: Runner = run_command,
) -> list[Check]:
    checks = [check_binary("gh"), check_binary("aws")]

    if checks[0].ok:
        gh_auth = check_gh_auth(runner)
        checks.append(gh_auth)
        if gh_auth.ok:
            checks.append(check_github_environment(repository, environment, runner))
            checks.extend(check_github_secrets(repository, runner))
            checks.extend(check_github_variables(repository, runner))

    if checks[1].ok:
        checks.append(check_aws_identity(runner, expected_aws_account_id))

    return checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check readiness for the SHS GitHub Actions AWS deploy workflow.",
    )
    parser.add_argument(
        "--repository",
        default=DEFAULT_REPOSITORY,
        help=f"GitHub repository, default {DEFAULT_REPOSITORY}.",
    )
    parser.add_argument(
        "--environment",
        default=DEFAULT_ENVIRONMENT,
        help=f"GitHub deployment environment, default {DEFAULT_ENVIRONMENT}.",
    )
    parser.add_argument(
        "--expected-aws-account-id",
        default=None,
        help="Optional AWS account ID expected from aws sts get-caller-identity.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    checks = run_preflight(
        repository=args.repository,
        environment=args.environment,
        expected_aws_account_id=args.expected_aws_account_id,
    )
    ok = all(check.ok for check in checks)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "checks": [check.__dict__ for check in checks],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("Deploy preflight summary")
        for check in checks:
            status = "ok" if check.ok else "missing"
            print(f"- {check.name}: {status} ({check.detail})")
        print(f"- Overall ok: {ok}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
