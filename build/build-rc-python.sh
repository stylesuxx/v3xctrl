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

sudo apt update
sudo apt install -y libssl-dev libbz2-dev libsqlite3-dev liblzma-dev \
    libreadline-dev libctypes-ocaml-dev libcurses-ocaml-dev libffi-dev

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
  ./configure ...
fi
make -j$(nproc)

# Move everything into place and package it
cd $PWD
cp -r "${SRC_DIR}" "$DEST_DIR"

#mkdir -p "${DEST_DIR}/usr/local"

make DESTDIR="${DEST_DIR}" install

dpkg-deb --build "$DEST_DIR"
lintian "${TMP_DIR}/${NAME}.deb"
