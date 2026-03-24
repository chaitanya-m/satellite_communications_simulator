#!/usr/bin/env bash
set -euo pipefail

# Pass the host uid/gid through to compose so results.txt is owned by the
# invoking user rather than root.
export HOST_UID="$(id -u)"
export HOST_GID="$(id -g)"

cleanup() {
  docker compose down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose up --build --abort-on-container-exit --exit-code-from study
