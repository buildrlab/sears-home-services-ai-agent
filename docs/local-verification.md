# Local Verification

Use this guide when validating changes in sears-home-services-ai-agent.

## Setup

```bash
No root package manifest detected.
```

## Fast Check

```bash
bash scripts/repo-health.sh
```

## Cheap Smoke Check

Use this when you only need to verify the universal guards without running package scripts or Terraform formatting.

```bash
SKIP_PACKAGE_SCRIPTS=1 SKIP_TERRAFORM=1 bash scripts/repo-health.sh
```

## Full Check

- Run the repo-health script and manually inspect changed docs or assets.

- `terraform fmt -check -recursive`

## Evidence To Capture

- Commands run and their result.
- Screenshots or recordings for user-facing UI changes.
- Generated artifact names for document, image, or asset changes.
- Any skipped checks with the reason they were skipped.
