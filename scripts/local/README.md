# Local Utility Scripts

These scripts are safe entry points for local development and reviewer checks.
They are designed to mirror GitHub Actions logic where practical.

## Docker App Lifecycle

Start the full local application with Docker Compose:

```bash
scripts/local/start-app.sh
```

Start only dependencies and backend:

```bash
scripts/local/start-app.sh --no-frontend
```

Stop SHS local Compose containers:

```bash
scripts/local/stop-containers.sh
```

Remove SHS local Compose containers, project volumes, and local Compose images:

```bash
scripts/local/tidy-docker.sh --force
```

Full Docker cleanup for the entire machine is intentionally explicit:

```bash
scripts/local/tidy-docker.sh --all-docker --force
```

## CI-Matching Checks

Backend lint:

```bash
scripts/local/lint-backend.sh
```

Backend CI-equivalent checks:

```bash
scripts/local/test-backend.sh
```

Frontend lint:

```bash
scripts/local/lint-frontend.sh
```

Frontend CI-equivalent checks:

```bash
scripts/local/test-frontend.sh
```

Scripts CI-equivalent checks:

```bash
scripts/local/check-scripts.sh
```

Reviewer local smoke flow:

```bash
scripts/local/smoke-local.sh
```
