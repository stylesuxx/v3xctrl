#! /bin/bash

NAME="v3xctrl"

ROOT_DIR="$(pwd)/build"
TMP_DIR="${ROOT_DIR}/tmp"
SRC_DIR="${ROOT_DIR}/${NAME}"

DEB_PATH="${TMP_DIR}/${NAME}.deb"
DEST_DIR="${TMP_DIR}/$NAME"

BASE_PATH="${DEST_DIR}/usr/share/$NAME"
SERVER_BASE_PATH="${BASE_PATH}/config-server/"
SERVER_LIB_PATH="${SERVER_BASE_PATH}/static/libs/"

GST_BASE_PATH="${BASE_PATH}/gst/"
PYTHON_LIB_PATH="${DEST_DIR}/opt/rc-venv/lib/python3.11/site-packages/"

# Clean up directory
sudo rm -r "${DEST_DIR}"

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

# Delete cache dirs
find "${DEST_DIR}" -type d -name '__pycache__' -exec rm -r {} +

# Fetch static files for the web server
curl -o "${SERVER_LIB_PATH}/jsoneditor.min.js" "https://raw.githubusercontent.com/jdorn/json-editor/master/dist/jsoneditor.min.js"
curl -o "${SERVER_LIB_PATH}/jquery.min.js" "https://code.jquery.com/jquery-3.6.0.min.js"
curl -o "${SERVER_LIB_PATH}/bootstrap3.min.css" "https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css"

# Build the deb package
gzip -9 -n "${DEST_DIR}/usr/share/doc/${NAME}/changelog"
sudo chown -R root:root "${DEST_DIR}"

dpkg-deb --build "${DEST_DIR}" "${DEB_PATH}"
lintian "${DEB_PATH}"
