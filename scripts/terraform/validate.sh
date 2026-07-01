#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

STACKS=(
  "infra/bootstrap"
  "infra/shared"
  "backend/infra"
  "frontend/infra"
)

for stack in "${STACKS[@]}"; do
  echo "==> terraform fmt: ${stack}"
  terraform -chdir="${ROOT_DIR}/${stack}" fmt -check -recursive

  echo "==> terraform init: ${stack}"
  terraform -chdir="${ROOT_DIR}/${stack}" init -backend=false

  echo "==> terraform validate: ${stack}"
  terraform -chdir="${ROOT_DIR}/${stack}" validate
done
