#! /bin/bash

NAME="rc-client"
PWD=$(pwd)
TMP_DIR="${PWD}/tmp"
SRC_DIR="${PWD}/${NAME}"
DEST_DIR="${TMP_DIR}/$NAME"
BASE_PATH="${PWD}/$NAME/usr/share/$NAME"

SERVER_BASE_PATH="${BASE_PATH}/config-server/"
SERVER_TEMPLATE_PATH="${SERVER_BASE_PATH}/templates/"
SERVER_LIB_PATH="${SERVER_BASE_PATH}/static/libs/"

GST_BASE_PATH="${BASE_PATH}/gst/"

# Clean up directory
sudo rm -rf "${SERVER_BASE_PATH}"

# Create dir structure for server
mkdir -p "${SERVER_BASE_PATH}"
mkdir -p "${SERVER_TEMPLATE_PATH}"
mkdir -p "${SERVER_LIB_PATH}"

# Move files into place
cp "${PWD}/../web-server/main.py" "${SERVER_BASE_PATH}"
cp "${PWD}/../web-server/templates/*" "${SERVER_TEMPLATE_PATH}"

# Fetch static files for the web server
curl -o "${SERVER_LIB_PATH}/jsoneditor.min.js" https://raw.githubusercontent.com/jdorn/json-editor/master/dist/jsoneditor.min.js
curl -o "${SERVER_LIB_PATH}/jquery.min.js" https://code.jquery.com/jquery-3.6.0.min.js
curl -o "${SERVER_LIB_PATH}/bootstrap3.min.css" https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css

### GSTREAMER ###
# Move gstreamer launcher in place
mkdir -p "${GST_BASE_PATH}"
cp "${PWD}/../bash/send_cam.sh "${GST_BASE_PATH}"

# Build the deb package
sudo rm -r $DEST_DIR
cp -r "${SRC_DIR}/" "$DEST_DIR"
gzip -9 -n "${DEST_DIR}/usr/share/doc/${NAME}/changelog"
sudo chown -R root:root "${DEST_DIR}"

dpkg-deb --build "${DEST_DIR}"
lintian $TMP_DIR/rc-client.deb
