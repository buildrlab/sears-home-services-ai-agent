# GitHub Branch Protection Runbook

Use `dev` as the integration branch and `main` as release-only. Do not merge
directly to either branch during implementation work.

## Current State

As of 2026-07-01, `dev` has no branch protection enabled. Apply protection after
the team confirms the exact required-check policy.

## Apply With Script

Dry run the recommended `dev` policy:

```bash
python3.14 scripts/github/configure_branch_protection.py
```

Apply it after `gh auth login` succeeds:

```bash
python3.14 scripts/github/configure_branch_protection.py --apply
```

The script requires the always-on Security CI jobs by default:

- `secret-scan`
- `dependency-audit`

Do not require path-filtered backend, frontend, Terraform, or scripts jobs until
an always-run aggregate check exists. Override the required checks with repeated
`--required-check` flags only after the policy changes.

## Recommended `dev` Protection

- Require pull request before merging.
- Require conversation resolution before merging.
- Require branches to be up to date before merging.
- Block force pushes.
- Block deletions.
- Allow admins to bypass only for emergency repository recovery.
- Use squash merge or regular merge consistently; avoid rebase-merging reviewed
  phase branches if it makes audit trails harder to follow.

Recommended required checks once workflow coverage is made always-on or an
aggregate required check is added:

- `backend`
- `frontend`
- `scripts`
- `secret-scan`
- `dependency-audit`
- `terraform (infra/bootstrap)`
- `terraform (infra/shared)`
- `terraform (backend/infra)`
- `terraform (frontend/infra)`
- `terraform-security`

The backend, frontend, Terraform, and scripts workflows currently use path
filters for cost control. Do not require those filtered checks until either the
filters are removed or an always-run aggregate quality gate exists; otherwise a
docs-only PR can be blocked waiting for checks that GitHub intentionally skipped.

## Recommended `main` Protection

- Require pull request before merging.
- Require `dev` to be the source branch for release PRs.
- Require the same status checks as `dev`.
- Block force pushes.
- Block deletions.
- Require signed tags for releases if release tagging is added.

## Apply Through GitHub UI

1. Open repository **Settings -> Branches**.
2. Add a branch protection rule for `dev`.
3. Add a branch protection rule for `main`.
4. Confirm required checks are not path-filtered before selecting them.
5. Save the rules and open a test PR to confirm the merge policy behaves as
   expected.
