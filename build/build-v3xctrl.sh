#! /bin/bash

NAME="v3xctrl"

# Use first argument as ROOT_DIR if provided, otherwise fallback to current working dir
ROOT_DIR="${1:-$(pwd)}"

TMP_DIR="${ROOT_DIR}/build/tmp"
SRC_DIR="${ROOT_DIR}/build/${NAME}"

DEB_PATH="${TMP_DIR}/${NAME}.deb"
DEST_DIR="${TMP_DIR}/$NAME"

BASE_PATH="${DEST_DIR}/usr/share/$NAME"
SERVER_BASE_PATH="${BASE_PATH}/config-server/"
SERVER_LIB_PATH="${SERVER_BASE_PATH}/static/libs/"

GST_BASE_PATH="${BASE_PATH}/gst/"
PYTHON_REQUIREMENTS="${ROOT_DIR}/requirements-client.txt"
PYTHON_LIB_PATH="${DEST_DIR}/opt/rc-venv/lib/python3.11/site-packages/"

# Create dir structure
mkdir -p "${TMP_DIR}"
mkdir -p "${BASE_PATH}"
mkdir -p "${SERVER_BASE_PATH}"
mkdir -p "${SERVER_LIB_PATH}"
mkdir -p "${GST_BASE_PATH}"
mkdir -p "${PYTHON_LIB_PATH}"

# Move files into place
cp -r "${SRC_DIR}/" "$TMP_DIR"
cp -r "${ROOT_DIR}/web-server/." "${SERVER_BASE_PATH}"
cp "${ROOT_DIR}/bash/transmit-stream.sh" "${GST_BASE_PATH}"
cp -r "${ROOT_DIR}/src/rpi_4g_streamer" "${PYTHON_LIB_PATH}"

# Fetch static files for the web server
curl -o "${SERVER_LIB_PATH}/jsoneditor.min.js" "https://raw.githubusercontent.com/jdorn/json-editor/master/dist/jsoneditor.min.js"
curl -o "${SERVER_LIB_PATH}/jquery.min.js" "https://code.jquery.com/jquery-3.6.0.min.js"
curl -o "${SERVER_LIB_PATH}/bootstrap3.min.css" "https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css"

# Install python dependencies
/opt/rc-python/bin/pip3.11 install \
  --no-cache-dir \
  --target "${PYTHON_LIB_PATH}" \
  -r "${PYTHON_REQUIREMENTS}"

# Build the deb package
gzip -9 -n "${DEST_DIR}/usr/share/doc/${NAME}/changelog"
chown -R root:root "${DEST_DIR}"

dpkg-deb --build "${DEST_DIR}" "${DEB_PATH}"
lintian "${DEB_PATH}"
