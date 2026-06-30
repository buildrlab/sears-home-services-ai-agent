# DNS Delegation Runbook

## Goal

Configure Sears DNS exactly like the existing BuildrLab `website` and `buildr-hq` projects.

## Account Boundary

- DNS account: `buildrlab-core`
- DNS account ID: `202612164956`
- Hosted zone: `buildrlab.com`
- Hosted zone ID: use the same parent hosted zone ID from the BuildrLab devops environment configuration.
- Sears workload account: to be confirmed before Phase 7.

## Required Records

Create records directly in the parent `buildrlab.com` hosted zone:

- `shs.buildrlab.com`
- `api.shs.buildrlab.com`
- `ws.shs.buildrlab.com`
- ACM DNS validation records for those hostnames.
- SES DNS validation records if SES identity verification requires them.

Do not create a child hosted zone for `shs.buildrlab.com` in the Sears account unless a later ADR explicitly changes this decision.

## Terraform Pattern

Use the same cross-account DNS model as the BuildrLab `website` and `buildr-hq` infrastructure:

- Default/workload provider manages Sears AWS resources.
- `aws.dns` provider assumes a Route 53 delegation role in `buildrlab-core`.
- `dns_account_id` is `202612164956`.
- `dns_sso_profile` is `buildrlab-core` for local Terraform runs.
- CI/CD uses OIDC and role assumption instead of SSO profiles.
- `hosted_zone_id`/`dns_hosted_zone_id` points to the existing `buildrlab.com` hosted zone.
- Cross-account mode creates records directly in the parent hosted zone.
- Cross-account mode creates no local Route 53 hosted zones in the Sears workload account.

Expected variable shape:

```hcl
dns_account_id    = "202612164956"
hosted_zone_id    = "<buildrlab.com hosted zone id>"
dns_sso_profile   = "buildrlab-core"
target_account_id = "<sears workload account id>"
```

Expected provider shape:

```hcl
provider "aws" {
  alias  = "dns"
  region = var.aws_region

  assume_role {
    role_arn     = "arn:aws:iam::${var.dns_account_id}:role/${var.project_name}-${var.environment}-route53-delegation"
    session_name = "terraform-sears-dns"
  }
}
```

## Setup Sequence

1. Confirm the Sears workload AWS account ID.
2. Add Sears environment tfvars using the same keys as `website` and `buildr-hq`: `target_account_id`, `dns_account_id`, `hosted_zone_id`, and `dns_sso_profile`.
3. Create or reuse a project/environment-specific Route 53 delegation role in `buildrlab-core`.
4. Configure Sears Terraform with a DNS provider alias that assumes that role.
5. Create ACM validation records through the DNS provider alias.
6. Create `shs`, `api.shs`, and `ws.shs` records through the DNS provider alias.
7. Confirm no Sears Terraform module creates a `shs.buildrlab.com` hosted zone.

## Verification

After deployment:

```bash
dig +short shs.buildrlab.com
dig +short api.shs.buildrlab.com
dig +short ws.shs.buildrlab.com
```

Then:

```bash
curl -f https://api.shs.buildrlab.com/health
```

## Completion Criteria

- Sears DNS uses the `buildrlab-core` hosted zone through a cross-account DNS provider.
- Required Sears records exist in the parent `buildrlab.com` hosted zone.
- ACM certificates validate through Route 53 DNS validation.
- GitHub Actions can assume the DNS delegation role.
- Terraform plans show no child hosted-zone creation for `shs.buildrlab.com`.
