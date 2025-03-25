#! /bin/bash

### CONFIG SERVER ###
# Add Config web-server to the package
BASE_PATH="./rc-client/usr/share/rc-client"
SERVER_BASE_PATH="${BASE_PATH}/config-server/"
TEMPLATE_PATH="${SERVER_BASE_PATH}/templates/"
LIB_PATH="${SERVER_BASE_PATH}/static/libs/"

# Clean up directory
rm -rf $SERVER_BASE_PATH

# Create dir structure for server
mkdir -p $SERVER_BASE_PATH
mkdir -p $TEMPLATE_PATH
mkdir -p $LIB_PATH

# Move files into place
cp ../web-server/main.py $SERVER_BASE_PATH
cp ../web-server/templates/* $TEMPLATE_PATH

# Fetch static files for the web server
curl -o "${LIB_PATH}/jsoneditor.min.js" https://raw.githubusercontent.com/jdorn/json-editor/master/dist/jsoneditor.min.js
curl -o "${LIB_PATH}/jquery.min.js" https://code.jquery.com/jquery-3.6.0.min.js
curl -o "${LIB_PATH}/bootstrap3.min.css" https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css

### GSTREAMER ###
# Move gstreamer launcher in place
GST_BASE_PATH="${BASE_PATH}/gst/"
mkdir -p $GST_BASE_PATH

cp ../bash/send_cam.sh $GST_BASE_PATH

# Build the deb package
TMP_DIR="./tmp"
TMP_CLIENT_DIR="${TMP_DIR}/rc-client"

sudo rm -r $TMP_DIR
mkdir -p $TMP_DIR

cp -r rc-client/ $TMP_DIR
gzip -9 -n $TMP_CLIENT_DIR/usr/share/doc/rc-client/changelog
#mv $TMP_CLIENT_DIR/usr/share/doc/rc-client/changelog.gz $TMP_CLIENT_DIR/usr/share/doc/rc-client/changelog.DEBIAN.gz
sudo chown -R root:root $TMP_CLIENT_DIR

dpkg-deb --build $TMP_CLIENT_DIR
lintian $TMP_DIR/rc-client.deb
