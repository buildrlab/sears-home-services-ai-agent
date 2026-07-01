from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "aws-deploy.yml"


class AwsDeployWorkflowTests(unittest.TestCase):
    def test_plan_mode_skips_dependent_stacks_when_shared_outputs_are_missing(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn('echo "shared_outputs_available=false" >> "$GITHUB_OUTPUT"', workflow)
        self.assertIn(
            'if ! shared_outputs="$(terraform -chdir=infra/shared output -json)"',
            workflow,
        )
        self.assertIn("Shared outputs are unavailable in plan mode", workflow)
        self.assertIn("Shared Terraform outputs are unavailable after shared apply", workflow)
        self.assertIn(
            "env.DEPLOY_MODE == 'apply' || steps.shared.outputs.shared_outputs_available == 'true'",
            workflow,
        )

    def test_shared_outputs_are_captured_from_single_json_payload(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn('shared_outputs="$(terraform -chdir=infra/shared output -json)"', workflow)
        self.assertIn("jq -r '.vpc_id.value'", workflow)
        self.assertIn("jq -c '.public_subnet_ids.value'", workflow)
        self.assertNotIn("terraform -chdir=infra/shared output -raw vpc_id", workflow)


if __name__ == "__main__":
    unittest.main()
