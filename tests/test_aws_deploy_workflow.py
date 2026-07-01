from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "aws-deploy.yml"
DESTROY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "aws-destroy.yml"


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

    def test_backend_outputs_are_captured_before_workload_role_steps(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        capture_index = workflow.index("- name: Capture backend outputs")
        assume_index = workflow.index("- name: Assume workload role for AWS CLI deploy steps")
        self.assertLess(capture_index, assume_index)
        self.assertIn(
            'backend_outputs="$(terraform -chdir=backend/infra output -json)"',
            workflow,
        )
        self.assertIn(
            "OPENAI_SECRET_ARN: ${{ steps.backend.outputs.openai_api_key_secret_arn }}",
            workflow,
        )
        self.assertIn(
            "TWILIO_SECRET_ARN: ${{ steps.backend.outputs.twilio_auth_token_secret_arn }}",
            workflow,
        )
        self.assertIn(
            "ECR_REPOSITORY_URL: ${{ steps.backend.outputs.ecr_repository_url }}",
            workflow,
        )
        self.assertNotIn(
            "MIGRATION_TASK_DEFINITION_ARN: "
            "${{ steps.backend.outputs.migration_task_definition_arn }}",
            workflow,
        )
        self.assertNotIn(
            'echo "migration_task_definition_arn=$(jq -r '
            "'.migration_task_definition_arn.value' <<< \"$backend_outputs\")",
            workflow,
        )
        self.assertNotIn("has(\"migration_task_definition_arn\") and", workflow)

    def test_migration_outputs_are_recaptured_after_backend_apply(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        apply_index = workflow.index("- name: Terraform backend apply")
        capture_index = workflow.index("- name: Capture backend deployment outputs")
        migration_index = workflow.index("- name: Run Alembic migration task")
        self.assertLess(apply_index, capture_index)
        self.assertLess(capture_index, migration_index)
        self.assertIn(
            'backend_deploy_outputs="$(terraform -chdir=backend/infra output -json)"',
            workflow,
        )
        self.assertIn(
            "ECS_TASKS_SECURITY_GROUP_ID: "
            "${{ steps.backend_deploy.outputs.ecs_tasks_security_group_id }}",
            workflow,
        )
        self.assertIn(
            "MIGRATION_TASK_DEFINITION_ARN: "
            "${{ steps.backend_deploy.outputs.migration_task_definition_arn }}",
            workflow,
        )
        self.assertNotIn("terraform -chdir=backend/infra output -raw", workflow)

    def test_frontend_outputs_are_captured_before_workload_upload_step(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        capture_index = workflow.index("- name: Capture frontend outputs")
        upload_index = workflow.index("- name: Upload frontend assets")
        self.assertLess(capture_index, upload_index)
        self.assertIn(
            'frontend_outputs="$(terraform -chdir=frontend/infra output -json)"',
            workflow,
        )
        self.assertIn(
            "FRONTEND_BUCKET_NAME: ${{ steps.frontend.outputs.frontend_bucket_name }}",
            workflow,
        )
        self.assertIn(
            "CLOUDFRONT_DISTRIBUTION_ID: ${{ steps.frontend.outputs.cloudfront_distribution_id }}",
            workflow,
        )
        self.assertNotIn("terraform -chdir=frontend/infra output -raw", workflow)

    def test_deploy_and_destroy_share_concurrency_group(self) -> None:
        deploy_workflow = WORKFLOW.read_text(encoding="utf-8")
        destroy_workflow = DESTROY_WORKFLOW.read_text(encoding="utf-8")
        concurrency_group = (
            "group: aws-environment-${{ github.event.inputs.environment || 'prod' }}"
        )

        self.assertIn(concurrency_group, deploy_workflow)
        self.assertIn(concurrency_group, destroy_workflow)

    def test_destroy_workflow_is_manual_and_guarded(self) -> None:
        workflow = DESTROY_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("type: choice", workflow)
        self.assertIn("- plan", workflow)
        self.assertIn("- destroy", workflow)
        self.assertIn(
            'expected_confirmation="destroy ${PROJECT_NAME} ${DEPLOY_ENVIRONMENT}"',
            workflow,
        )
        self.assertIn('if [ "$DESTROY_CONFIRMATION" != "$expected_confirmation" ]; then', workflow)
        self.assertIn('if [ "$DELETE_DATA" != "true" ]; then', workflow)
        self.assertIn(
            "The shared Terraform state bucket is not destroyed by this workflow",
            workflow,
        )

    def test_destroy_workflow_tears_down_in_reverse_stack_order(self) -> None:
        workflow = DESTROY_WORKFLOW.read_text(encoding="utf-8")

        frontend_destroy = workflow.index("- name: Terraform frontend destroy")
        backend_destroy = workflow.index("- name: Terraform backend destroy")
        shared_destroy = workflow.index("- name: Terraform shared destroy")
        self.assertLess(frontend_destroy, backend_destroy)
        self.assertLess(backend_destroy, shared_destroy)
        self.assertIn("enable_alb_deletion_protection: false", workflow)
        self.assertIn("database_deletion_protection: false", workflow)
        self.assertIn("upload_bucket_force_destroy: $delete_data", workflow)
        self.assertIn("frontend_bucket_force_destroy: $delete_data", workflow)
        self.assertIn("ecr_force_delete: $delete_data", workflow)


if __name__ == "__main__":
    unittest.main()
