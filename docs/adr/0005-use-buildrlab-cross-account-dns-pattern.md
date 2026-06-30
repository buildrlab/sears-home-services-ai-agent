# ADR 0005: Use BuildrLab Cross-Account DNS Pattern

## Status

Accepted

## Context

The main `buildrlab.com` Route 53 hosted zone lives in the `buildrlab-core` AWS account `202612164956`.

BuildrLab projects such as `website` and `buildr-hq` already use a cross-account DNS pattern:

- Environment tfvars include `dns_account_id = "202612164956"`.
- Environment tfvars include the parent `buildrlab.com` hosted zone ID.
- Local Terraform uses `dns_sso_profile = "buildrlab-core"`.
- CI/CD assumes a project/environment-specific Route 53 delegation role in the DNS account.
- Application DNS records are created directly in the existing `buildrlab.com` hosted zone through an `aws.dns` provider alias.
- No local child hosted zones are created in the workload accounts for this mode.

The Sears project needs:

- `shs.buildrlab.com`
- `api.shs.buildrlab.com`
- `ws.shs.buildrlab.com`

## Decision

Follow the same BuildrLab cross-account DNS pattern used by `website` and `buildr-hq`.

The Sears workload account will not create a Route 53 child hosted zone for `shs.buildrlab.com`.

Instead, Terraform will:

- Configure a DNS provider alias that assumes a Route 53 delegation role in `buildrlab-core`.
- Use the existing parent `buildrlab.com` hosted zone ID.
- Create Sears records directly in that parent hosted zone.
- Keep the DNS account role scoped to Route 53 record management for the shared hosted zone.

Expected variable shape:

```hcl
dns_account_id      = "202612164956"
hosted_zone_id      = "<buildrlab.com hosted zone id>"
dns_sso_profile     = "buildrlab-core"
dns_account_role_arn = "arn:aws:iam::202612164956:role/<project-env>-route53-delegation"
```

## Consequences

- Sears DNS setup matches the established BuildrLab deployment model.
- The parent `buildrlab.com` hosted zone remains owned by `buildrlab-core`.
- The Sears app account can deploy application records through explicit cross-account role assumption.
- Terraform must clearly separate the Sears workload provider from the DNS provider.
- DNS plans must be reviewed carefully so Sears modules only create/update the intended `shs.buildrlab.com`, `api.shs.buildrlab.com`, ACM validation, SES validation, and related project records.

## Alternatives Considered

- Create a child hosted zone for `shs.buildrlab.com` in the Sears account and add an `NS` delegation in the parent zone. This is a valid AWS model, but it does not match the existing BuildrLab `website` and `buildr-hq` pattern.
- Manage DNS manually in the Route 53 console. Rejected because durable AWS infrastructure should be Terraform-managed.

## Review Date

Review during Phase 7 before implementing Terraform providers and DNS records.
