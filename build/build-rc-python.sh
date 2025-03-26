#/bin/bash
# Build a custom Python version and package it into a Debian package.
VERSION=3.11.11

NAME='rc-python'
PWD=$(pwd)
TMP_DIR="${PWD}/tmp"
SRC_DIR="${PWD}/${NAME}"
DEST_DIR="${TMP_DIR}/${NAME}"
BASE_PATH="$PWD/tmp/python"
DOWNLOAD_PATH="${BASE_PATH}/Python-${VERSION}.tgz"
UNPACK_PATH="${BASE_PATH}/Python-${VERSION}"
DONWLOAD_URL="https://www.python.org/ftp/python/${VERSION}/Python-${VERSION}.tgz"

SWAP_SIZE=8192
SWAP_PATH="/etc/dphys-swapfile"

# Increase swap size
sudo dphys-swapfile swapoff
sudo sed -i \
  -e "s/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=${SWAP_SIZE}/" \
  -e "s/^#CONF_MAXSWAP=.*/CONF_MAXSWAP=${SWAP_SIZE}/" \
  $SWAP_PATH
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Install build dependencies
sudo apt update
sudo apt install -y build-essential libssl-dev libbz2-dev libsqlite3-dev \
  liblzma-dev libreadline-dev libctypes-ocaml-dev libcurses-ocaml-dev \
  libffi-dev chroot

mkdir -p ${BASE_PATH}
cd ${BASE_PATH}

# Only download if the unpacked directory doesn't exist
if ! [ -d "$UNPACK_PATH" ]; then
  wget "https://www.python.org/ftp/python/${VERSION}/Python-${VERSION}.tgz"
  tar -xzf ${DOWNLOAD_PATH} -C .
fi

# Will only be fully built, if it has not been before, otherwise the compiled
# files will be used.
cd $UNPACK_PATH
if [ ! -f "Makefile" ]; then
  CFLAGS="-O3 -s" LDFLAGS="-s" ./configure \
    --prefix=/usr \
    --enable-shared \
    --enable-optimizations \
    --without-doc-strings \
    --disable-test-modules
fi
make -j$(nproc)

# Move everything into place and package it
sudo rm -r "$DEST_DIR"
cd $PWD
cp -r "${SRC_DIR}/" "$DEST_DIR"

#mkdir -p "${DEST_DIR}/usr/local"

make DESTDIR="${DEST_DIR}" altinstall
chroot "${DEST_DIR}" /usr/bin/python3.11 -m ensurepip --upgrade
gzip -9 -n "$DEST_DIR/usr/share/doc/$NAME/changelog"
sudo chown -R root:root "$DEST_DIR"

dpkg-deb --build "$DEST_DIR"
lintian "${TMP_DIR}/${NAME}.deb"
