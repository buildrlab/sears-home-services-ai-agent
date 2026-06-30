# Shared Terraform

This directory is for shared AWS resources.

Expected resources:

- Cross-account Route 53 provider/role wiring for `buildrlab-core` account `202612164956`.
- Route 53 records for `shs.buildrlab.com`, `api.shs.buildrlab.com`, and `ws.shs.buildrlab.com` created directly in the existing `buildrlab.com` hosted zone.
- ACM and SES DNS validation records in the existing `buildrlab.com` hosted zone.
- GitHub OIDC IAM role.
- Shared VPC/subnets/security groups.
- Shared IAM policy boundaries where appropriate.

Match the `website` and `buildr-hq` pattern: cross-account DNS provider against the parent hosted zone, no Sears child hosted zone.
