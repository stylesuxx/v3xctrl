#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${REPO_ROOT}/build/tmp/viewer-flatpak"
OUTPUT_DIR="${REPO_ROOT}/build/tmp"
SRC_DIR="${REPO_ROOT}/src"

VERSION="${VERSION:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD)}"

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}" "${OUTPUT_DIR}"

# Generate version file for the build
echo "VERSION = \"${VERSION}\"" > "${SRC_DIR}/v3xctrl_ui/_version.py"

# Build Flatpak
flatpak-builder \
  --force-clean \
  --repo="${BUILD_DIR}/repo" \
  "${BUILD_DIR}/build" \
  "${REPO_ROOT}/build/flatpak/com.v3xctrl.viewer.yml"

# Export as bundle file
flatpak build-bundle \
  "${BUILD_DIR}/repo" \
  "${OUTPUT_DIR}/v3xctrl-viewer-linux-${VERSION}.flatpak" \
  com.v3xctrl.viewer

echo "Flatpak bundle created: ${OUTPUT_DIR}/v3xctrl-viewer-linux-${VERSION}.flatpak"
