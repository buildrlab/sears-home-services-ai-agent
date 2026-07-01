#!/usr/bin/env bash

set -Eeuo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

ALL_DOCKER=0
FORCE=0
PRUNE_BUILD_CACHE=0

usage() {
  cat <<'USAGE'
Usage: scripts/local/tidy-docker.sh --force [--all-docker] [--prune-build-cache]

Removes Docker resources.

Default scope with --force:
  Removes SHS local Compose containers, project volumes, local Compose images,
  and orphan containers for COMPOSE_PROJECT_NAME=shs-ai-agent-local.

Host-wide scope:
  --all-docker --force removes every Docker container, image, and volume on this
  machine. Use only when you intentionally want a full Docker cleanup.

Options:
  --force              Required for any deletion.
  --all-docker         Remove all Docker containers, images, and volumes.
  --prune-build-cache  Also prune Docker build cache.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --force)
      FORCE=1
      ;;
    --all-docker)
      ALL_DOCKER=1
      ;;
    --prune-build-cache)
      PRUNE_BUILD_CACHE=1
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

if [ "${FORCE}" -ne 1 ]; then
  usage >&2
  echo "" >&2
  echo "Refusing to delete Docker resources without --force." >&2
  exit 2
fi

if [ "${ALL_DOCKER}" -eq 1 ]; then
  container_ids="$(docker container ls -aq)"
  if [ -n "${container_ids}" ]; then
    docker container rm -f ${container_ids}
  fi

  image_ids="$(docker image ls -aq)"
  if [ -n "${image_ids}" ]; then
    docker image rm -f ${image_ids}
  fi

  volume_names="$(docker volume ls -q)"
  if [ -n "${volume_names}" ]; then
    docker volume rm -f ${volume_names}
  fi
else
  compose down --remove-orphans --volumes --rmi local
fi

if [ "${PRUNE_BUILD_CACHE}" -eq 1 ]; then
  docker builder prune -f
fi
