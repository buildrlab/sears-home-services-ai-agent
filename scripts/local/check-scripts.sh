#!/usr/bin/env bash

set -Eeuo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
  cat <<'USAGE'
Usage: scripts/local/check-scripts.sh

Matches Scripts CI:
- installs Ruff 0.15.20
- runs Ruff over scripts and tests
- compiles scripts and tests with Python 3.14
- runs unittest discovery under tests/
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

python_bin="${PYTHON_BIN:-python3.14}"
"${python_bin}" -m pip install --upgrade pip
"${python_bin}" -m pip install ruff==0.15.20
(cd "${REPO_ROOT}" && "${python_bin}" -m ruff check scripts tests)
(cd "${REPO_ROOT}" && PYTHONPYCACHEPREFIX=/private/tmp/shs-pycache "${python_bin}" -m compileall scripts tests)
(cd "${REPO_ROOT}" && PYTHONDONTWRITEBYTECODE=1 "${python_bin}" -m unittest discover -s tests)
