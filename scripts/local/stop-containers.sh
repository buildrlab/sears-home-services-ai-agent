#!/usr/bin/env bash

set -Eeuo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

ALL_DOCKER=0
FORCE=0

usage() {
  cat <<'USAGE'
Usage: scripts/local/stop-containers.sh [--all-docker --force]

Stops local SHS Docker Compose containers by default.

Options:
  --all-docker   Stop every running Docker container on this machine.
  --force        Required with --all-docker.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --all-docker)
      ALL_DOCKER=1
      ;;
    --force)
      FORCE=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

require_command docker

if [ "${ALL_DOCKER}" -eq 1 ]; then
  if [ "${FORCE}" -ne 1 ]; then
    echo "--all-docker requires --force." >&2
    exit 2
  fi
  container_ids="$(docker container ls -q)"
  if [ -n "${container_ids}" ]; then
    docker container stop ${container_ids}
  else
    echo "No running Docker containers to stop."
  fi
  exit 0
fi

compose stop
