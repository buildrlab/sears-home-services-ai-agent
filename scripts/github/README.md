# GitHub Scripts

Scripts in this folder automate repository setup that is not AWS infrastructure.
They must support dry-run behavior before mutating GitHub state.

## `configure_deploy.py`

Creates or updates the GitHub deployment environment values required by
`.github/workflows/aws-deploy.yml`.

Dry run:

```bash
python3.14 scripts/github/configure_deploy.py \
  --aws-devops-account-id "<devops-account-id>"
```

Apply environment and variables:

```bash
python3.14 scripts/github/configure_deploy.py \
  --aws-devops-account-id "<devops-account-id>" \
  --apply
```

Apply environment, variables, and secrets from environment variables:

```bash
export AWS_DEVOPS_ROLE_ARN="arn:aws:iam::<devops-account-id>:role/<github-oidc-role>"
export OPENAI_API_KEY="<redacted>"
export TWILIO_AUTH_TOKEN="<redacted>"

python3.14 scripts/github/configure_deploy.py \
  --aws-devops-account-id "<devops-account-id>" \
  --include-secrets \
  --apply
```

The script uses environment-scoped GitHub variables/secrets for `prod` by
default. It never prints secret values or passes them as command-line
arguments; apply mode sends each secret to `gh secret set` through stdin.

## `configure_branch_protection.py`

Creates or updates the conservative `dev` branch protection policy.

Dry run:

```bash
python3.14 scripts/github/configure_branch_protection.py
```

Apply protection:

```bash
python3.14 scripts/github/configure_branch_protection.py --apply
```

By default, the script requires the always-on Security CI jobs:

- `secret-scan`
- `dependency-audit`

It does not require path-filtered backend, frontend, Terraform, or scripts jobs
until an always-run aggregate required check exists. Use repeated
`--required-check` flags to override the required check list after the policy
changes.
