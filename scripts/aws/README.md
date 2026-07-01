# AWS Scripts

Self-documenting scripts for AWS deployment verification live here. They must not
create durable infrastructure; Terraform and GitHub Actions own deployment.

## `remote_smoke.py`

Runs post-deploy smoke checks against the public API and frontend:

- `GET /healthz` on the API must return the SHS backend health payload.
- `GET /` on the frontend must return the React shell.
- `GET /uploads/remote-smoke-token` must return the React shell through the
  CloudFront SPA fallback.

Usage:

```bash
python3.14 scripts/aws/remote_smoke.py \
  --api-base-url https://api.shs.buildrlab.com \
  --frontend-base-url https://shs.buildrlab.com
```

Machine-readable output:

```bash
python3.14 scripts/aws/remote_smoke.py \
  --api-base-url https://api.shs.buildrlab.com \
  --frontend-base-url https://shs.buildrlab.com \
  --json
```

## `deploy_preflight.py`

Runs read-only checks before triggering `.github/workflows/aws-deploy.yml`:

- `gh` is installed and authenticated.
- GitHub deployment environment `prod` exists.
- Required deployment secrets are present.
- Required deployment variables are present and match the documented values.
- `aws` is installed and can resolve caller identity.

Usage:

```bash
python3.14 scripts/aws/deploy_preflight.py
```

Machine-readable output:

```bash
python3.14 scripts/aws/deploy_preflight.py --json
```

If you know which AWS account the local credentials should resolve to, add:

```bash
python3.14 scripts/aws/deploy_preflight.py \
  --expected-aws-account-id "<account-id>"
```
