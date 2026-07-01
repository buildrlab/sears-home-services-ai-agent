#!/usr/bin/env python3
"""Configure GitHub deployment environment variables and secrets."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

DEFAULT_REPOSITORY = "buildrlab/sears-home-services-ai-agent"
DEFAULT_ENVIRONMENT = "prod"

FIXED_VARIABLES = {
    "SHS_WORKLOAD_ACCOUNT_ID": "710045722740",
    "SHS_DNS_ACCOUNT_ID": "202612164956",
    "SHS_HOSTED_ZONE_ID": "Z05781442GINHB3A5IJXK",
    "TF_STATE_BUCKET": "buildrlab-terraform-state",
}

SECRET_NAMES = (
    "AWS_DEVOPS_ROLE_ARN",
    "OPENAI_API_KEY",
    "TWILIO_AUTH_TOKEN",
)


@dataclass(frozen=True)
class PlannedCommand:
    label: str
    args: tuple[str, ...]
    stdin_value: str | None = None

    def display(self) -> str:
        command = " ".join(self.args)
        if self.stdin_value is None:
            return command
        return f"{command} <stdin:redacted>"


@dataclass(frozen=True)
class ConfigurationPlan:
    commands: list[PlannedCommand]
    missing: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing


class Runner(Protocol):
    def __call__(self, args: Sequence[str], stdin: str | None) -> int:
        """Run a command and return its exit code."""


def run_command(args: Sequence[str], stdin: str | None) -> int:
    completed = subprocess.run(  # noqa: S603
        list(args),
        check=False,
        input=stdin,
        text=stdin is not None,
    )
    return completed.returncode


def build_plan(
    *,
    repository: str,
    environment_name: str,
    aws_devops_account_id: str | None,
    include_secrets: bool,
    environ: Mapping[str, str],
) -> ConfigurationPlan:
    commands = [
        PlannedCommand(
            label="ensure_environment",
            args=(
                "gh",
                "api",
                "--method",
                "PUT",
                f"repos/{repository}/environments/{environment_name}",
            ),
        )
    ]
    missing: list[str] = []

    variables = dict(FIXED_VARIABLES)
    if aws_devops_account_id:
        variables["AWS_DEVOPS_ACCOUNT_ID"] = aws_devops_account_id
    else:
        missing.append("AWS_DEVOPS_ACCOUNT_ID")

    for name, value in sorted(variables.items()):
        commands.append(
            PlannedCommand(
                label=f"set_variable_{name}",
                args=(
                    "gh",
                    "variable",
                    "set",
                    name,
                    "--repo",
                    repository,
                    "--env",
                    environment_name,
                    "--body",
                    value,
                ),
            )
        )

    if include_secrets:
        for name in SECRET_NAMES:
            value = environ.get(name)
            if not value:
                missing.append(name)
                continue
            commands.append(
                PlannedCommand(
                    label=f"set_secret_{name}",
                    args=(
                        "gh",
                        "secret",
                        "set",
                        name,
                        "--repo",
                        repository,
                        "--env",
                        environment_name,
                    ),
                    stdin_value=value,
                )
            )

    return ConfigurationPlan(commands=commands, missing=missing)


def apply_plan(plan: ConfigurationPlan, runner: Runner = run_command) -> int:
    if not plan.ok:
        return 1
    for command in plan.commands:
        returncode = runner(command.args, command.stdin_value)
        if returncode != 0:
            return returncode
    return 0


def print_plan(plan: ConfigurationPlan, *, apply: bool) -> None:
    action = "Applying" if apply else "Dry run"
    print(f"GitHub deploy configuration: {action}")
    for command in plan.commands:
        print(f"- {command.label}: {command.display()}")
    if plan.missing:
        print("- Missing required values:")
        for name in plan.missing:
            print(f"  - {name}")
    print(f"- Overall ok: {plan.ok}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create/update the GitHub deployment environment variables and optional "
            "secrets required by .github/workflows/aws-deploy.yml."
        ),
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
        "--aws-devops-account-id",
        default=os.environ.get("AWS_DEVOPS_ACCOUNT_ID"),
        help="BuildrLab devops/control AWS account ID. Can also be set with AWS_DEVOPS_ACCOUNT_ID.",
    )
    parser.add_argument(
        "--include-secrets",
        action="store_true",
        help=(
            "Also set AWS_DEVOPS_ROLE_ARN, OPENAI_API_KEY, and TWILIO_AUTH_TOKEN "
            "from environment variables."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the plan. Without this flag, the script only prints the planned commands.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    plan = build_plan(
        repository=args.repository,
        environment_name=args.environment,
        aws_devops_account_id=args.aws_devops_account_id,
        include_secrets=args.include_secrets,
        environ=os.environ,
    )
    print_plan(plan, apply=args.apply)
    if not args.apply:
        return 0 if plan.ok else 1
    return apply_plan(plan)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
