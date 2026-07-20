# Release Readiness

Use this checklist before tagging, deploying, or publishing sears-home-services-ai-agent.

## Required

- [ ] Working tree only contains intentional changes.
- [ ] `bash scripts/repo-health.sh` has passed locally or in the manual GitHub workflow.
- [ ] Dependency lockfiles are updated when package manifests change.
- [ ] Public docs reflect changed commands, configuration, or behavior.
- [ ] User-facing changes include tests or explicit manual verification notes.

## Stack-Specific

- [ ] No web-route verification required for this repository.
- [ ] Playwright coverage is updated for changed critical flows.
- [ ] Terraform formatting has passed and plans were reviewed before apply.
- [ ] Generated assets were opened or rendered before delivery.

## Rollback Notes

- Record the previous deployed version or commit SHA.
- Keep environment-specific changes separate from application changes where practical.
- Capture any required manual cleanup steps before release.
