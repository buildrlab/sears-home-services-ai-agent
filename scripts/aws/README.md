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

## `final_live_smoke.py`

Runs the final reviewer-readiness checks against the deployed API. It creates a
disposable diagnostic session, posts Twilio webhooks with production-valid
signatures, sends an SES upload-link email to a verified recipient, uploads a
tiny PNG through the presigned S3 POST, runs image analysis, and verifies the
session history event.

Usage:

```bash
AWS_PROFILE=sears python3.14 scripts/aws/final_live_smoke.py \
  --api-base-url https://api.shs.buildrlab.com \
  --email-to no-reply@shs.buildrlab.com
```

The default recipient is under the verified `shs.buildrlab.com` SES domain.
Use another recipient only after SES production access is approved or the
recipient is verified in the SES sandbox.

## `deploy_preflight.py`

Runs read-only checks before triggering `.github/workflows/aws-deploy.yml`:

- `gh` is installed and authenticated.
- GitHub deployment environment `prod` exists.
- Required deployment secrets are present in the GitHub environment.
- Required deployment variables are present in the GitHub environment and match
  the documented values.
- The protected branch has the conservative required policy applied.
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

To check a non-default GitHub environment or protected branch:

```bash
python3.14 scripts/aws/deploy_preflight.py \
  --environment prod \
  --branch dev
```
