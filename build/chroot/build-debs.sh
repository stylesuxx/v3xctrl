#!/bin/bash
LOCALE="en_US.UTF-8"

PARAMS=""
SKIP_DEPS=false
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --skip-deps|-s)
      PARAMS="--skip-deps"
      SKIP_DEPS=true
    ;;
    *) echo "Unknown parameter: $1"; exit 1 ;;
  esac
  shift
done

# Ensure locale is configured and generated only once
if [ ! -f "/usr/lib/locale/locale-archive" ]; then
  # First time setup: add locale to config and generate
  if ! grep -q "^${LOCALE} UTF-8$" /etc/locale.gen 2>/dev/null; then
    echo "$LOCALE UTF-8" >> /etc/locale.gen
  fi
  locale-gen
  echo "LANG=$LOCALE" > /etc/default/locale
  update-locale LANG=$LOCALE
fi

# Change to working directory
cd /src

if [ "$SKIP_DEPS" = false ]; then
  echo '[CHROOT] Updating OS and Installing dependencies'
  apt update
  apt upgrade -y
  apt install -y \
    build-essential \
    curl \
    ca-certificates \
    dphys-swapfile \
    libbz2-dev \
    libcairo2-dev \
    libctypes-ocaml-dev \
    libcurses-ocaml-dev \
    libdb-dev \
    libffi-dev \
    libgdbm-dev \
    libgdbm-compat-dev \
    libgirepository1.0-dev \
    liblzma-dev \
    libncursesw5-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    lintian \
    tk-dev \
    uuid-dev \
    zlib1g-dev
fi

# Build v3xctrl-python only if it does not exist yet
if ! dpkg -s v3xctrl-python >/dev/null 2>&1; then
  echo '[CHROOT] Building Python'
  ./build/build-python.sh /src
  apt install -y ./build/tmp/v3xctrl-python.deb
fi

echo '[CHROOT] Building v3xctrl'
./build/build-v3xctrl.sh /src ${PARAMS}

echo '[CHROOT] Package build done...'
