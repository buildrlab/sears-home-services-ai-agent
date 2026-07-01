from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_MAIN = REPO_ROOT / "backend" / "infra" / "main.tf"


class TerraformStaticAnalysisTests(unittest.TestCase):
    def test_ses_dkim_route53_records_use_static_for_each_keys(self) -> None:
        main_tf = BACKEND_MAIN.read_text(encoding="utf-8")

        self.assertNotIn(
            "for_each = toset(aws_ses_domain_dkim.email.dkim_tokens)",
            main_tf,
        )
        self.assertIn("for index in range(3)", main_tf)
        self.assertIn("aws_ses_domain_dkim.email.dkim_tokens[index]", main_tf)


if __name__ == "__main__":
    unittest.main()
