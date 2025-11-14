#!/bin/bash
LOCALE="en_US.UTF-8"

# Parse arguments
SKIP_DEPS=false
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --skip-deps|-s) SKIP_DEPS=true ;;
    *) echo "Unknown parameter: $1"; exit 1 ;;
  esac
  shift
done

# Change to working directory
cd /src

if [ "$SKIP_DEPS" = false ]; then
  echo '[CHROOT] Updating OS and Installing dependencies'
  apt update
  apt upgrade -y
  apt install -y \
    curl build-essential libssl-dev libbz2-dev libsqlite3-dev ca-certificates \
    liblzma-dev libreadline-dev libffi-dev libgdbm-dev libgdbm-compat-dev \
    libdb-dev uuid-dev zlib1g-dev libncursesw5-dev tk-dev \
    libctypes-ocaml-dev libcurses-ocaml-dev dphys-swapfile lintian
fi

# Build v3xctrl-python only if it does not exist yet
if ! dpkg -s v3xctrl-python >/dev/null 2>&1; then
  echo '[CHROOT] Fixing locale'
  echo "$LOCALE UTF-8" >> /etc/locale.gen
  locale-gen
  echo "LANG=$LOCALE" > /etc/default/locale
  update-locale LANG=$LOCALE

  echo '[CHROOT] Building Python'
  ./build/build-python.sh /src
  apt install -y ./build/tmp/v3xctrl-python.deb
fi

echo '[CHROOT] Building v3xctrl'
./build/build-v3xctrl.sh /src

echo '[CHROOT] Package build done...'
