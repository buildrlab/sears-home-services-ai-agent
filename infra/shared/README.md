# Shared Terraform

This directory manages shared AWS resources for the Sears workload account.

Managed resources:

- VPC.
- Public and private subnets across two Availability Zones.
- Internet gateway.
- Single NAT gateway for private Fargate egress to AWS APIs, Twilio, and OpenAI.
- ECS cluster with container insights enabled.

Match the `website` and `buildr-hq` pattern: cross-account DNS provider against the parent hosted zone, no Sears child hosted zone.

Backend and frontend DNS records are created in their dedicated stacks using
the same `aws.dns` provider alias, because those records depend on ALB and
CloudFront outputs.

## Local Validation

```bash
terraform init -backend=false
terraform validate
```

## Local Plan

```bash
cp backend.hcl.example backend.hcl
cp prod.tfvars.example prod.tfvars
terraform init -backend-config=backend.hcl
terraform plan -var-file=prod.tfvars
```
