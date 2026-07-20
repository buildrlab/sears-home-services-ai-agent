#!/usr/bin/env bash
set -u -o pipefail

failures=0

info() { printf '[repo-health] %s\n' "$*"; }
warn() { printf '[repo-health][warn] %s\n' "$*" >&2; }
fail() { printf '[repo-health][fail] %s\n' "$*" >&2; failures=$((failures + 1)); }

run_check() {
  local label="$1"
  shift
  info "running $label"
  "$@"
  local status=$?
  if [ "$status" -ne 0 ]; then
    fail "$label failed with exit code $status"
  fi
}

has_node_script() {
  local script_name="$1"
  [ -f package.json ] || return 1
  command -v node >/dev/null 2>&1 || return 1
  node - "$script_name" <<'NODE'
const fs = require("fs");
const script = process.argv[2];
try {
  const pkg = JSON.parse(fs.readFileSync("package.json", "utf8"));
  process.exit(pkg.scripts && Object.prototype.hasOwnProperty.call(pkg.scripts, script) ? 0 : 1);
} catch {
  process.exit(1);
}
NODE
}

package_manager() {
  if [ -f pnpm-lock.yaml ]; then
    printf 'pnpm'
  elif [ -f yarn.lock ]; then
    printf 'yarn'
  else
    printf 'npm'
  fi
}

run_package_script() {
  local script_name="$1"
  has_node_script "$script_name" || return 0
  if [ "${SKIP_PACKAGE_SCRIPTS:-0}" = "1" ]; then
    warn "skipping package script $script_name because SKIP_PACKAGE_SCRIPTS=1"
    return 0
  fi
  local pm
  pm="$(package_manager)"
  if [ ! -d node_modules ] && [ "${CI:-}" != "true" ] && [ "${STRICT:-0}" != "1" ]; then
    warn "skipping $pm run $script_name because dependencies are not installed"
    return 0
  fi
  if ! command -v "$pm" >/dev/null 2>&1; then
    warn "skipping $pm run $script_name because $pm is not installed"
    return 0
  fi
  run_check "$pm run $script_name" "$pm" run "$script_name"
}

info "checking for unresolved merge markers"
if git grep -n -E '^(<<<<<<< .+|=======|>>>>>>> .+)$' -- ':!pnpm-lock.yaml' ':!package-lock.json' ':!yarn.lock' ':!node_modules/**' ':!**/node_modules/**' >/tmp/repo-health-conflicts.$$ 2>/dev/null; then
  cat /tmp/repo-health-conflicts.$$
  fail "merge conflict markers are present"
fi
rm -f /tmp/repo-health-conflicts.$$

info "checking for tracked private env files"
tracked_env_files="$(git ls-files | grep -E '(^|/)\.env(\.|$)' | grep -Ev '(\.example|\.sample|\.template)$' || true)"
if [ -n "$tracked_env_files" ]; then
  printf '%s\n' "$tracked_env_files"
  if [ "${STRICT_ENV_FILES:-0}" = "1" ]; then
    fail "private env files are tracked"
  else
    warn "tracked env files found; set STRICT_ENV_FILES=1 to fail this check"
  fi
fi

if [ -f package.json ]; then
  if command -v node >/dev/null 2>&1; then
    run_check "package.json parse" node -e 'JSON.parse(require("fs").readFileSync("package.json", "utf8"))'
  else
    warn "node is not installed; package.json checks skipped"
  fi
fi

if command -v rg >/dev/null 2>&1; then
  info "checking markdown for empty links"
  if rg -n '\]\(\s*\)' README.md docs Docs .github 2>/dev/null; then
    fail "empty markdown links are present"
  fi
else
  warn "ripgrep is not installed; markdown empty-link check skipped"
fi

for script_name in secrets:scan scan:secrets security:scan safety:scan lint typecheck type-check tsc test; do
  run_package_script "$script_name"
done

if [ "${SKIP_TERRAFORM:-0}" = "1" ]; then
  warn "skipping Terraform formatting because SKIP_TERRAFORM=1"
elif find . -path './.git' -prune -o -path './node_modules' -prune -o -name '*.tf' -print -quit | grep -q .; then
  if command -v terraform >/dev/null 2>&1; then
    run_check "terraform fmt -check -recursive" terraform fmt -check -recursive
  else
    warn "terraform files found but terraform is not installed"
  fi
fi

if [ "$failures" -ne 0 ]; then
  fail "$failures repo-health check(s) failed"
  exit 1
fi

info "all available repo-health checks passed"
