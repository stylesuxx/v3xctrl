#/bin/bash
# Build a custom Python version and package it into a Debian package.
set -e

VERSION=3.11.11

NAME='rc-python'

# Use first argument as ROOT_DIR if provided, otherwise fallback to current working dir
ROOT_DIR="${1:-$(pwd)}"

TMP_DIR="${ROOT_DIR}/build/tmp"
SRC_DIR="${ROOT_DIR}/build/${NAME}"

DEB_PATH="${TMP_DIR}/${NAME}.deb"
DEST_DIR="${TMP_DIR}/${NAME}"

BASE_PATH="$ROOT_DIR/tmp/python"
DOWNLOAD_PATH="${BASE_PATH}/Python-${VERSION}.tgz"
UNPACK_PATH="${BASE_PATH}/Python-${VERSION}"
DONWLOAD_URL="https://www.python.org/ftp/python/${VERSION}/Python-${VERSION}.tgz"
PREFIX="/opt/rc-python"

# Clean up previous build (only relevant when re-building on dev setup)
# In workflows we start with a clean environment anyway
rm -rf "${DEST_DIR}"
rm -f "${DEB_PATH}"

# Create dir structure
mkdir -p "${TMP_DIR}"
mkdir -p "${BASE_PATH}"
cd ${BASE_PATH}

# Only download if the unpacked directory doesn't exist
if ! [ -d "$UNPACK_PATH" ]; then
  curl -o "${DOWNLOAD_PATH}" "https://www.python.org/ftp/python/${VERSION}/Python-${VERSION}.tgz"
  tar -xzf "${DOWNLOAD_PATH}" -C "${BASE_PATH}"
fi

# Will only be fully built, if it has not been before, otherwise the compiled
# files will be used.
cd $UNPACK_PATH
if [ ! -f "Makefile" ]; then
  CFLAGS="-O3 -s" LDFLAGS="-s -Wl,-rpath,/opt/rc-python/lib" ./configure \
    --prefix="${PREFIX}" \
    --enable-shared \
    --without-doc-strings \
    --disable-test-modules \
    --with-ensurepip=install
fi
make -j$(nproc)

# Move everything into place and package it
cp -r "${SRC_DIR}/" "$DEST_DIR"

make DESTDIR="${DEST_DIR}" altinstall
gzip -9 -n "${DEST_DIR}/usr/share/doc/${NAME}/changelog"
find "${DEST_DIR}/opt/rc-python" -name '__pycache__' -type d -exec rm -rf {} +
find "${DEST_DIR}/opt/rc-python/lib" -name '*.so*' -exec chmod 644 {} +
chown -R root:root "${DEST_DIR}"

dpkg-deb --build "${DEST_DIR}" "${DEB_PATH}"
lintian "${DEB_PATH}"
