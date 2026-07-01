#!/usr/bin/env python3
"""Final readiness audit for local artifacts and live deployment gates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    "PLAN.md",
    "PROMPTS.md",
    "docs/technical-design.md",
    "docs/submission-hardening.md",
    "docs/runbooks/local-testing.md",
    "docs/runbooks/aws-testing.md",
    "scripts/reviewer/local_smoke.py",
    "scripts/aws/remote_smoke.py",
    "scripts/aws/deploy_preflight.py",
    "scripts/github/configure_deploy.py",
    "scripts/github/configure_branch_protection.py",
    ".github/dependabot.yml",
    ".github/workflows/aws-deploy.yml",
)

REQUIRED_ADRS = (
    "docs/adr/0001-use-postgresql-for-scheduling.md",
    "docs/adr/0002-use-twilio-conversationrelay-with-gather-fallback.md",
    "docs/adr/0003-use-openai-for-agent-and-vision.md",
    "docs/adr/0004-use-scripted-twilio-provisioning.md",
    "docs/adr/0005-use-buildrlab-cross-account-dns-pattern.md",
    "docs/adr/0006-run-python-backend-on-fargate-with-separate-migration-task.md",
    "docs/adr/0007-split-terraform-stacks-with-s3-lockfile.md",
)

REQUIRED_PLAN_MARKERS = (
    "Phase 0: Repository and Governance Foundation",
    "Phase 0.5: Twilio Access and Provisioning",
    "Phase 1: Backend Foundation",
    "Phase 2: Scheduling Domain",
    "Phase 3: Diagnostic Agent",
    "Phase 4: Twilio Voice",
    "Phase 5: Visual Diagnosis",
    "Phase 6: Frontend",
    "Phase 7: Infrastructure",
    "Phase 8: CI/CD and Remote Validation",
    "Phase 9: Submission Hardening",
)


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    ok: bool
    detail: str


class Runner(Protocol):
    def __call__(self, args: Sequence[str]) -> CommandResult:
        """Run a command and return captured output."""


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


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def check_required_paths(repo_root: Path, paths: Sequence[str], name: str) -> ReadinessCheck:
    missing = [path for path in paths if not (repo_root / path).is_file()]
    return ReadinessCheck(
        name=name,
        ok=not missing,
        detail="present" if not missing else f"missing: {', '.join(missing)}",
    )


def check_plan_markers(repo_root: Path) -> ReadinessCheck:
    plan_path = repo_root / "PLAN.md"
    if not plan_path.is_file():
        return ReadinessCheck("plan_phase_tracking", False, "PLAN.md missing")
    content = plan_path.read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_PLAN_MARKERS if marker not in content]
    return ReadinessCheck(
        name="plan_phase_tracking",
        ok=not missing,
        detail="all phase markers present" if not missing else f"missing: {', '.join(missing)}",
    )


def check_prompt_log(repo_root: Path) -> ReadinessCheck:
    prompts_path = repo_root / "PROMPTS.md"
    if not prompts_path.is_file():
        return ReadinessCheck("prompt_log", False, "PROMPTS.md missing")
    content = prompts_path.read_text(encoding="utf-8")
    if "Pending in this branch" in content:
        return ReadinessCheck("prompt_log", False, "contains pending branch marker")
    return ReadinessCheck("prompt_log", True, "present with no pending branch marker")


def parse_preflight_output(result: CommandResult) -> tuple[bool, str]:
    raw = (result.stdout or result.stderr).strip()
    if not raw:
        return False, "deploy_preflight.py produced no output"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, f"deploy_preflight.py did not return JSON: {exc}"
    if not isinstance(payload, dict):
        return False, "deploy_preflight.py JSON was not an object"
    ok = payload.get("ok") is True
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return False, "deploy_preflight.py JSON omitted checks"
    failures = [
        str(check.get("name", "unknown"))
        for check in checks
        if isinstance(check, dict) and check.get("ok") is not True
    ]
    if ok and not failures:
        return True, "deploy preflight passed"
    return False, f"deploy preflight blocked: {', '.join(failures) or 'unknown'}"


def check_deploy_preflight(repo_root: Path, runner: Runner) -> ReadinessCheck:
    result = runner(
        (
            sys.executable,
            str(repo_root / "scripts" / "aws" / "deploy_preflight.py"),
            "--json",
        )
    )
    ok, detail = parse_preflight_output(result)
    if result.returncode != 0 and ok:
        return ReadinessCheck(
            "live_deploy_preflight",
            False,
            f"preflight returned {result.returncode} despite ok payload",
        )
    return ReadinessCheck("live_deploy_preflight", ok, detail)


def build_checks(repo_root: Path, runner: Runner = run_command) -> list[ReadinessCheck]:
    return [
        check_required_paths(repo_root, REQUIRED_FILES, "required_project_files"),
        check_required_paths(repo_root, REQUIRED_ADRS, "required_adrs"),
        check_plan_markers(repo_root),
        check_prompt_log(repo_root),
        check_deploy_preflight(repo_root, runner),
    ]


def print_text(checks: Sequence[ReadinessCheck]) -> None:
    print("Final readiness summary")
    for check in checks:
        status = "ok" if check.ok else "blocked"
        print(f"- {check.name}: {status} ({check.detail})")
    print(f"- Overall ok: {all(check.ok for check in checks)}")


def print_json(checks: Sequence[ReadinessCheck]) -> None:
    print(
        json.dumps(
            {
                "ok": all(check.ok for check in checks),
                "checks": [check.__dict__ for check in checks],
            },
            indent=2,
            sort_keys=True,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit final submission readiness. This is read-only and fails "
            "closed until live GitHub/AWS deployment gates pass."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=str(repo_root_from_script()),
        help="Repository root. Defaults to the current script's repository.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    checks = build_checks(repo_root)
    if args.json:
        print_json(checks)
    else:
        print_text(checks)
    return 0 if all(check.ok for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
