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

PYTHON_REQUIREMENTS="${BUILD_DIR}/requirements/streamer.txt"
PYTHON_LIB_PATH="${DEST_DIR}/opt/v3xctrl-venv/lib/python3.11/site-packages/"

WEB_DIST_PATH="${PYTHON_LIB_PATH}/v3xctrl_web/dist"

NVM_VERSION="v0.40.3"
NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

# Clean up previous build (only relevant when re-building on dev setup)
# In workflows we start with a clean environment anyway
if [ "$SKIP_DEPS" = false ]; then
  rm -rf "${DEST_DIR}"
fi
rm -f "${DEB_PATH}"

# Create dir structure
mkdir -p "${TMP_DIR}"
mkdir -p "${BASE_PATH}"
mkdir -p "${PYTHON_LIB_PATH}"

# Move files into place
cp -r "${SRC_DIR}/" "$TMP_DIR"

# Resolve package version
# VERSION env var can be: "1.0.0", "1.0.0-RC1", or unset (dev build).
# Converts to Debian-compatible versions using tilde for pre-release:
#   1.0.0-RC1  -> 1.0.0~rc1
#   1.0.0      -> 1.0.0
#   (unset)    -> <base>~dev.<timestamp>.<hash>  (from DEBIAN/control + git)
CONTROL_FILE="${DEST_DIR}/DEBIAN/control"
BASE_VERSION=$(grep '^Version:' "${CONTROL_FILE}" | awk '{print $2}')

if [ -n "${VERSION:-}" ]; then
  # Explicit version: convert "1.0.0-RC1" to "1.0.0~rc1"
  DEB_VERSION=$(echo "$VERSION" | sed 's/-\(.*\)/~\L\1/')
else
  # Dev build: append ~dev.<timestamp>.<short hash>
  TIMESTAMP=$(date -u +%Y%m%d%H%M%S)
  SHORT_HASH=$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo "unknown")
  DEB_VERSION="${BASE_VERSION}~dev.${TIMESTAMP}.${SHORT_HASH}"
fi

echo "[BUILD] Package version: ${DEB_VERSION}"
sed -i "s/^Version: .*/Version: ${DEB_VERSION}/" "${CONTROL_FILE}"

# Move python dependencies into place
cp -r "${ROOT_DIR}/src/v3xctrl_control" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_gst" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_helper" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_punch" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_tcp" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_relay" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_telemetry" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_self_test" "${PYTHON_LIB_PATH}"
cp -r "${ROOT_DIR}/src/v3xctrl_web" "${PYTHON_LIB_PATH}"

if [ "$SKIP_DEPS" = false ]; then
  # Install nvm and Node.js LTS
  if [ ! -s "${NVM_DIR}/nvm.sh" ]; then
    curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash
  fi
  . "${NVM_DIR}/nvm.sh"
  nvm install --lts
  COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack enable

  (
    cd "${ROOT_DIR}/client"
    yarn cache clean
    yarn install
  )

  # Install python dependencies
  v3xctrl-pip install \
    --no-cache-dir \
    --target "${PYTHON_LIB_PATH}" \
    -r "${PYTHON_REQUIREMENTS}"
fi

# Source nvm for node/yarn availability (needed even with --skip-deps)
. "${NVM_DIR}/nvm.sh"

# Build the React client in embedded mode and copy into package
(cd "${ROOT_DIR}/client" && VITE_EMBEDDED=true yarn build)
mkdir -p "${WEB_DIST_PATH}"
cp -r "${ROOT_DIR}/client/dist/"* "${WEB_DIST_PATH}/"

# Copy swagger-ui files from node_modules into the dist
SWAGGER_UI_SRC="${ROOT_DIR}/client/node_modules/swagger-ui-dist"
mkdir -p "${WEB_DIST_PATH}/swagger-ui"
cp "${SWAGGER_UI_SRC}/swagger-ui-bundle.js" "${WEB_DIST_PATH}/swagger-ui/"
cp "${SWAGGER_UI_SRC}/swagger-ui-standalone-preset.js" "${WEB_DIST_PATH}/swagger-ui/"
cp "${SWAGGER_UI_SRC}/swagger-ui.css" "${WEB_DIST_PATH}/swagger-ui/"

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
