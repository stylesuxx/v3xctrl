#! /bin/bash

NAME="v3xctrl"
PWD=$(pwd)
TMP_DIR="${PWD}/tmp"
SRC_DIR="${PWD}/${NAME}"
DEST_DIR="${TMP_DIR}/$NAME"

BASE_PATH="${DEST_DIR}/usr/share/$NAME"

SERVER_BASE_PATH="${BASE_PATH}/config-server/"
SERVER_LIB_PATH="${SERVER_BASE_PATH}/static/libs/"

GST_BASE_PATH="${BASE_PATH}/gst/"
PYTHON_LIB_PATH="${DEST_DIR}/opt/rc-venv/lib/python3.11/site-packages/"

cp -r "${SRC_DIR}/" "$TMP_DIR"

# Create dir structure
mkdir -p "${BASE_PATH}"
mkdir -p "${SERVER_BASE_PATH}"
mkdir -p "${SERVER_LIB_PATH}"
mkdir -p "${GST_BASE_PATH}"
mkdir -p "${PYTHON_LIB_PATH}"

# Move files into place
cp -r "${PWD}/web-server/." "${SERVER_BASE_PATH}"
cp "${PWD}/bash/transmit-stream.sh" "${GST_BASE_PATH}"
cp -r "${PWD}/src/rpi_4g_streamer" ${PYTHON_LIB_PATH}

# Delete cache dirs
find "${DEST_DIR}" -type d -name '__pycache__' -exec rm -r {} +

# Fetch static files for the web server
curl -o "${SERVER_LIB_PATH}/jsoneditor.min.js" "https://raw.githubusercontent.com/jdorn/json-editor/master/dist/jsoneditor.min.js"
curl -o "${SERVER_LIB_PATH}/jquery.min.js" "https://code.jquery.com/jquery-3.6.0.min.js"
curl -o "${SERVER_LIB_PATH}/bootstrap3.min.css" "https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css"


# Build the deb package
gzip -9 -n "${DEST_DIR}/usr/share/doc/${NAME}/changelog"
sudo chown -R root:root "${DEST_DIR}"

dpkg-deb --build "${DEST_DIR}"
lintian "${TMP_DIR}/${NAME}.deb"
