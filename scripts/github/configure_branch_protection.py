#!/usr/bin/env python3
"""Configure GitHub branch protection for the integration branch."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

DEFAULT_REPOSITORY = "buildrlab/sears-home-services-ai-agent"
DEFAULT_BRANCH = "dev"
DEFAULT_REQUIRED_CHECKS = ("secret-scan", "dependency-audit")


@dataclass(frozen=True)
class ProtectionPlan:
    repository: str
    branch: str
    required_checks: tuple[str, ...]
    payload: dict[str, Any]

    @property
    def command(self) -> tuple[str, ...]:
        return (
            "gh",
            "api",
            "--method",
            "PUT",
            f"repos/{self.repository}/branches/{self.branch}/protection",
            "--input",
            "-",
        )

    def display_command(self) -> str:
        return " ".join(self.command)


class Runner(Protocol):
    def __call__(self, args: Sequence[str], stdin: str) -> int:
        """Run a command and return its exit code."""


def run_command(args: Sequence[str], stdin: str) -> int:
    completed = subprocess.run(  # noqa: S603
        list(args),
        check=False,
        input=stdin,
        text=True,
    )
    return completed.returncode


def build_payload(required_checks: Sequence[str]) -> dict[str, Any]:
    checks = tuple(required_checks)
    return {
        "required_status_checks": (
            {
                "strict": True,
                "contexts": list(checks),
            }
            if checks
            else None
        ),
        "enforce_admins": False,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 0,
            "require_last_push_approval": False,
        },
        "restrictions": None,
        "required_conversation_resolution": True,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "lock_branch": False,
        "allow_fork_syncing": True,
    }


def build_plan(
    *,
    repository: str,
    branch: str,
    required_checks: Sequence[str],
) -> ProtectionPlan:
    checks = tuple(dict.fromkeys(required_checks))
    return ProtectionPlan(
        repository=repository,
        branch=branch,
        required_checks=checks,
        payload=build_payload(checks),
    )


def apply_plan(plan: ProtectionPlan, runner: Runner = run_command) -> int:
    return runner(plan.command, json.dumps(plan.payload, sort_keys=True))


def print_plan(plan: ProtectionPlan, *, apply: bool) -> None:
    action = "Applying" if apply else "Dry run"
    print(f"GitHub branch protection: {action}")
    print(f"- Repository: {plan.repository}")
    print(f"- Branch: {plan.branch}")
    if plan.required_checks:
        print("- Required checks:")
        for check in plan.required_checks:
            print(f"  - {check}")
    else:
        print("- Required checks: none")
    print(f"- Command: {plan.display_command()}")
    print("- Payload:")
    print(json.dumps(plan.payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create/update conservative GitHub branch protection. Dry-run by "
            "default; pass --apply to mutate GitHub."
        ),
    )
    parser.add_argument(
        "--repository",
        default=DEFAULT_REPOSITORY,
        help=f"GitHub repository, default {DEFAULT_REPOSITORY}.",
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=f"Branch to protect, default {DEFAULT_BRANCH}.",
    )
    parser.add_argument(
        "--required-check",
        action="append",
        dest="required_checks",
        help=(
            "Required status/check context. Can be repeated. Defaults to the "
            "always-on Security CI jobs."
        ),
    )
    parser.add_argument(
        "--no-required-checks",
        action="store_true",
        help="Protect the branch without requiring status checks.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the plan. Without this flag, the script only prints it.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.no_required_checks and args.required_checks:
        parser.error("--no-required-checks cannot be combined with --required-check.")
    required_checks = (
        ()
        if args.no_required_checks
        else tuple(args.required_checks or DEFAULT_REQUIRED_CHECKS)
    )
    plan = build_plan(
        repository=args.repository,
        branch=args.branch,
        required_checks=required_checks,
    )
    print_plan(plan, apply=args.apply)
    if not args.apply:
        return 0
    return apply_plan(plan)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
