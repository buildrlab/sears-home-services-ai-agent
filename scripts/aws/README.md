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
