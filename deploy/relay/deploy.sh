#!/bin/bash
#
# Copy the working tree to the relay host and restart the services.
#
# Run from the development machine. State (relay.db, users.json) lives in
# /var/lib/v3xctrl on the host, outside the tree, which is what makes --delete
# safe here.
set -euo pipefail

DEFAULT_REMOTE_ROOT="/opt/v3xctrl"

usage() {
  cat >&2 <<USAGE
Usage: deploy.sh <user@host> [--root PATH] [--restart UNIT] [--no-restart] [--dry-run]

  --root        destination tree on the host (default: ${DEFAULT_REMOTE_ROOT})
  --restart     unit to restart afterwards (default: v3xctrl-relay.target)
  --no-restart  copy only, for the first deploy before any units exist
  --dry-run     show what rsync would transfer, change nothing
USAGE
  exit 2
}

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Only what the relay host runs. The repository also carries build artifacts,
# the Android app and the web client, which together are several gigabytes and
# have no business on the relay.
PATHS=(src stats-server deploy build/requirements)

target="${1:-}"
[[ -n "${target}" ]] || usage
shift

remote_root="${DEFAULT_REMOTE_ROOT}"
restart_unit="v3xctrl-relay.target"
dry_run=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) remote_root="${2:-}"; shift 2 ;;
    --restart) restart_unit="${2:-}"; shift 2 ;;
    --no-restart) restart_unit=""; shift ;;
    --dry-run) dry_run="--dry-run"; shift ;;
    *) usage ;;
  esac
done

sources=()
for relative_path in "${PATHS[@]}"; do
  if [[ ! -e "${SOURCE_ROOT}/${relative_path}" ]]; then
    echo "Missing from the source tree: ${relative_path}" >&2
    exit 1
  fi
  # The /./ marker tells --relative where the preserved path begins.
  sources+=("${SOURCE_ROOT}/./${relative_path}")
done

rsync -a --delete --relative ${dry_run} \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.mypy_cache' \
  --exclude '.pytest_cache' \
  "${sources[@]}" "${target}:${remote_root}/"

if [[ -n "${dry_run}" ]]; then
  echo "Dry run, nothing restarted"
  exit 0
fi

if [[ -z "${restart_unit}" ]]; then
  echo "Copied to ${target}:${remote_root}, nothing restarted"
  exit 0
fi

ssh "${target}" "sudo systemctl restart ${restart_unit}"
echo "Deployed to ${target}:${remote_root} and restarted ${restart_unit}"
