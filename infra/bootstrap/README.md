# Terraform Bootstrap

This directory is for the one-time Terraform state bootstrap resources.

Managed resources:

- S3 bucket for Terraform state.
- Native S3 state locking through backend `use_lockfile = true`.
- Baseline bucket encryption and public access blocks.

Run locally before any remote backend exists:

```bash
cp prod.tfvars.example prod.tfvars
terraform init
terraform apply -var-file=prod.tfvars
```

After bootstrap, initialize other stacks with their `backend.hcl` files:

```bash
cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl
```

The BuildrLab devops account already uses the shared
`buildrlab-terraform-state` bucket pattern. If that bucket already exists, do
not recreate it from this stack; import it or use the existing central bootstrap
state.
