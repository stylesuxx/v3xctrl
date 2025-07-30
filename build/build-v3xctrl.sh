#! /bin/bash

NAME="v3xctrl"

# Use first argument as ROOT_DIR if provided, otherwise fallback to current working dir
ROOT_DIR="${1:-$(pwd)}"

BUILD_DIR="${ROOT_DIR}/build"
TMP_DIR="${BUILD_DIR}/tmp"
SRC_DIR="${BUILD_DIR}/packages/${NAME}"

DEB_PATH="${TMP_DIR}/${NAME}.deb"
DEST_DIR="${TMP_DIR}/$NAME"

BASE_PATH="${DEST_DIR}/usr/share/$NAME"
SERVER_BASE_PATH="${BASE_PATH}/config-server/"
SERVER_LIB_PATH="${SERVER_BASE_PATH}/static/libs/"

PYTHON_REQUIREMENTS="${BUILD_DIR}/requirements/streamer.txt"
PYTHON_LIB_PATH="${DEST_DIR}/opt/v3xctrl-venv/lib/python3.11/site-packages/"

# Clean up previous build (only relevant when re-building on dev setup)
# In workflows we start with a clean environment anyway
rm -r "${DEST_DIR}"
rm "${DEB_PATH}"

# Create dir structure
mkdir -p "${TMP_DIR}"
mkdir -p "${BASE_PATH}"
mkdir -p "${SERVER_BASE_PATH}"
mkdir -p "${SERVER_LIB_PATH}"
mkdir -p "${PYTHON_LIB_PATH}"

# Move files into place
cp -r "${SRC_DIR}/" "$TMP_DIR"
cp -r "${ROOT_DIR}/web-server/." "${SERVER_BASE_PATH}"

# Move python dependencies into place
cp -r "${ROOT_DIR}/src/v3xctrl_control" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_helper" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_punch" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_udp_relay" "${PYTHON_LIB_PATH}"

# Fetch static files for the web server
curl -o "${SERVER_LIB_PATH}/jsoneditor.min.js" "https://raw.githubusercontent.com/jdorn/json-editor/master/dist/jsoneditor.min.js"
curl -o "${SERVER_LIB_PATH}/jquery.min.js" "https://code.jquery.com/jquery-3.6.0.min.js"
curl -o "${SERVER_LIB_PATH}/bootstrap3.min.css" "https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css"

# Install python dependencies
v3xctrl-pip install \
  --no-cache-dir \
  --target "${PYTHON_LIB_PATH}" \
  -r "${PYTHON_REQUIREMENTS}"

# Remove cache dirs
find "${PYTHON_LIB_PATH}" -name '__pycache__' -type d -exec rm -rf {} +

# Build the deb package
gzip -9 -n "${DEST_DIR}/usr/share/doc/${NAME}/changelog"
chown -R root:root "${DEST_DIR}"

dpkg-deb --build "${DEST_DIR}" "${DEB_PATH}"
lintian "${DEB_PATH}"
