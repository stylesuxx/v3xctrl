#!/usr/bin/env bash
set -euo pipefail

# Generates the python-deps.json file for the Flatpak manifest.
#
# Prerequisites:
#   pip install flatpak-pip-generator
#   (from https://github.com/nickvdp/flatpak-pip-generator or the
#    flatpak-builder-tools repo)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

flatpak-pip-generator \
  --requirements-file="${REPO_ROOT}/build/requirements/viewer-flatpak.txt" \
  --output="${SCRIPT_DIR}/python-deps"

echo "Generated ${SCRIPT_DIR}/python-deps.json"
