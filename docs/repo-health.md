# Repository Health

This repo-health profile documents the checks that should run before review or release.

## Snapshot

| Item | Value |
| --- | --- |
| Repository | sears-home-services-ai-agent |
| Detected stack | Playwright, Python, Terraform or infra, asset/document outputs |
| Package manager | none |
| Root package | no |
| Terraform or infra files | yes |

## Default Gate

```bash
bash scripts/repo-health.sh
```

## Useful Commands

- `bash scripts/repo-health.sh`

## Review Standard

- No unresolved merge markers.
- Tracked env files are reviewed; set `STRICT_ENV_FILES=1` to fail on them.
- Markdown links should not be empty placeholders.
- Package manifests must parse cleanly.
- Existing lint, typecheck, test, and security scripts should pass before release.
