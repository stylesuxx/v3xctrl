#! /bin/bash
set -e

NAME="v3xctrl"

ROOT_DIR="$(pwd)"
SKIP_DEPS=false

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --skip-deps|-s)
      SKIP_DEPS=true
      ;;
    -*)
      echo "Unknown parameter: $1"
      exit 1
      ;;
    *)
      ROOT_DIR="$1"
      ;;
  esac
  shift
done

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
if [ "$SKIP_DEPS" = false ]; then
  rm -rf "${DEST_DIR}"
fi
rm -f "${DEB_PATH}"

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
cp -r "${ROOT_DIR}/src/v3xctrl_gst" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_helper" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_punch" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_udp_relay" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_telemetry" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_self_test" "${PYTHON_LIB_PATH}"

if [ "$SKIP_DEPS" = false ]; then
  # Fetch static files for the web server
  curl -o "${SERVER_LIB_PATH}/jsoneditor.min.js" "https://raw.githubusercontent.com/jdorn/json-editor/master/dist/jsoneditor.min.js"
  curl -o "${SERVER_LIB_PATH}/jquery.min.js" "https://code.jquery.com/jquery-3.6.0.min.js"
  curl -o "${SERVER_LIB_PATH}/bootstrap3.min.css" "https://cdn.jsdelivr.net/npm/bootstrap@3.3.7/dist/css/bootstrap.min.css"

  # Install python dependencies
  v3xctrl-pip install \
    --no-cache-dir \
    --target "${PYTHON_LIB_PATH}" \
    -r "${PYTHON_REQUIREMENTS}"
fi

# Remove cache dirs
find "${PYTHON_LIB_PATH}" -name '__pycache__' -type d -exec rm -rf {} +
find "${PYTHON_LIB_PATH}" -name "*.so" -exec strip --strip-unneeded {} \; 2>/dev/null || true

# Fix file permissions
chmod 440 "${DEST_DIR}/etc/sudoers.d/010_v3xctrl"

# Build the deb package
gzip -9 -n -f "${DEST_DIR}/usr/share/doc/${NAME}/changelog"
chown -R root:root "${DEST_DIR}"

dpkg-deb --build "${DEST_DIR}" "${DEB_PATH}"
lintian "${DEB_PATH}" || true

