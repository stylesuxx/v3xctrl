#/bin/bash
# Build a custom Python version and package it into a Debian package.
VERSION=3.11.4

PWD=$(pwd)
BASE_PATH="$PWD/tmp/python"
DOWNLOAD_PATH="${BASE_PATH}/Python-${VERSION}.tgz"
UNPACK_PATH="${BASE_PATH}/Python-${VERSION}"
DONWLOAD_URL="https://www.python.org/ftp/python/${VERSION}/Python-${VERSION}.tgz"

sudo apt update
sudo apt install -y libssl-dev libbz2-dev libsqlite3-dev liblzma-dev \
    libreadline-dev libctypes-ocaml-dev libcurses-ocaml-dev libffi-dev

mkdir -p ${BASE_PATH}
cd ${BASE_PATH}

if ! [ -f $UNPACK_PATH ]; then
  wget "https://www.python.org/ftp/python/${VERSION}/Python-${VERSION}.tgz"
  tar -xzf ${DOWNLOAD_PATH} -C .
fi

cd $UNPACK_PATH
./configure --enable-optimizations
make -j4

cd $PWD
cp -r ${UNPACK_PATH}/pkg/usr/local/${VERSION} ./rc-python/usr/local/
