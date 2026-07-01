from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_MAIN = REPO_ROOT / "backend" / "infra" / "main.tf"
BACKEND_VARIABLES = REPO_ROOT / "backend" / "infra" / "variables.tf"
FRONTEND_MAIN = REPO_ROOT / "frontend" / "infra" / "main.tf"
FRONTEND_VARIABLES = REPO_ROOT / "frontend" / "infra" / "variables.tf"


class TerraformStaticAnalysisTests(unittest.TestCase):
    def test_ses_dkim_route53_records_use_static_for_each_keys(self) -> None:
        main_tf = BACKEND_MAIN.read_text(encoding="utf-8")

        self.assertNotIn(
            "for_each = toset(aws_ses_domain_dkim.email.dkim_tokens)",
            main_tf,
        )
        self.assertIn("for index in range(3)", main_tf)
        self.assertIn("aws_ses_domain_dkim.email.dkim_tokens[index]", main_tf)

    def test_destroy_escape_hatches_default_to_safe_values(self) -> None:
        backend_main = BACKEND_MAIN.read_text(encoding="utf-8")
        backend_variables = BACKEND_VARIABLES.read_text(encoding="utf-8")
        frontend_main = FRONTEND_MAIN.read_text(encoding="utf-8")
        frontend_variables = FRONTEND_VARIABLES.read_text(encoding="utf-8")

        self.assertIn("force_delete         = var.ecr_force_delete", backend_main)
        self.assertIn("force_destroy = var.upload_bucket_force_destroy", backend_main)
        self.assertIn("force_destroy = var.frontend_bucket_force_destroy", frontend_main)
        self.assertIn('variable "ecr_force_delete"', backend_variables)
        self.assertIn('variable "upload_bucket_force_destroy"', backend_variables)
        self.assertIn('variable "frontend_bucket_force_destroy"', frontend_variables)
        self.assertIn("default     = false", backend_variables)
        self.assertIn("default     = false", frontend_variables)

    def test_api_task_can_send_upload_links_to_any_customer_email(self) -> None:
        main_tf = BACKEND_MAIN.read_text(encoding="utf-8")

        self.assertIn('"ses:SendEmail"', main_tf)
        self.assertIn("Resource = \"*\"", main_tf)


if __name__ == "__main__":
    unittest.main()
