from __future__ import annotations

import os
import stat
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SCRIPTS_DIR = REPO_ROOT / "scripts" / "local"

EXECUTABLE_SCRIPTS = (
    "start-app.sh",
    "stop-containers.sh",
    "tidy-docker.sh",
    "lint-backend.sh",
    "test-backend.sh",
    "lint-frontend.sh",
    "test-frontend.sh",
    "check-scripts.sh",
    "smoke-local.sh",
)


class LocalUtilityScriptTests(unittest.TestCase):
    def test_expected_local_scripts_exist_and_are_executable(self) -> None:
        for script_name in EXECUTABLE_SCRIPTS:
            script_path = LOCAL_SCRIPTS_DIR / script_name
            with self.subTest(script=script_name):
                self.assertTrue(script_path.is_file())
                mode = script_path.stat().st_mode
                self.assertTrue(mode & stat.S_IXUSR, f"{script_name} is not executable")

    def test_tidy_script_requires_force_for_deletion(self) -> None:
        script = (LOCAL_SCRIPTS_DIR / "tidy-docker.sh").read_text(encoding="utf-8")

        self.assertIn("Refusing to delete Docker resources without --force", script)
        self.assertIn("--all-docker --force", script)
        self.assertIn("docker container rm -f", script)
        self.assertIn("docker image rm -f", script)
        self.assertIn("docker volume rm -f", script)

    def test_start_script_runs_migrations_before_app_services(self) -> None:
        script = (LOCAL_SCRIPTS_DIR / "start-app.sh").read_text(encoding="utf-8")

        migrate_index = script.index("compose run --rm backend-migrate")
        backend_index = script.index("services=(backend)")
        self.assertLess(migrate_index, backend_index)
        self.assertIn("shs-ai-agent-uploads-local", script)

    def test_no_local_script_uses_windows_line_endings(self) -> None:
        for script_name in (*EXECUTABLE_SCRIPTS, "_common.sh"):
            script_path = LOCAL_SCRIPTS_DIR / script_name
            with self.subTest(script=script_name):
                self.assertNotIn(b"\r\n", script_path.read_bytes())

    def test_common_helper_uses_repo_scoped_compose_project_name(self) -> None:
        script = (LOCAL_SCRIPTS_DIR / "_common.sh").read_text(encoding="utf-8")

        self.assertIn("COMPOSE_PROJECT_NAME", script)
        self.assertIn("shs-ai-agent-local", script)
        self.assertIn("docker-compose.local.yml", script)

    def test_smoke_script_wraps_reviewer_smoke_defaults(self) -> None:
        script = (LOCAL_SCRIPTS_DIR / "smoke-local.sh").read_text(encoding="utf-8")

        self.assertIn("scripts/reviewer/local_smoke.py", script)
        self.assertIn("http://127.0.0.1:8000", script)
        self.assertIn("http://127.0.0.1:5173", script)
        self.assertIn("--api-only", script)

    def test_scripts_are_not_world_writable(self) -> None:
        for script_name in (*EXECUTABLE_SCRIPTS, "_common.sh"):
            script_path = LOCAL_SCRIPTS_DIR / script_name
            with self.subTest(script=script_name):
                self.assertFalse(script_path.stat().st_mode & stat.S_IWOTH)

    def test_readme_documents_each_executable_script(self) -> None:
        readme = (LOCAL_SCRIPTS_DIR / "README.md").read_text(encoding="utf-8")

        for script_name in EXECUTABLE_SCRIPTS:
            with self.subTest(script=script_name):
                self.assertIn(f"scripts/local/{script_name}", readme)


if __name__ == "__main__":
    os.chdir(REPO_ROOT)
    unittest.main()
