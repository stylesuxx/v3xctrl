#! /bin/bash
#
# Command is expected to be run from the root of the project diretory.
#
# This script is meant for easy package rebuild and install during development
# on the RPi directly. Prefered method is to build on the host machine via
# chroot, this is just for convenience and people who don't run Linux on their
# dev machines for whatever strange reason.
set -e

if [[ "$EUID" -ne 0 ]]; then
  echo "[${NAME}] Please run as root (use sudo)" >&2
  exit 1
fi

NAME="v3xctrl"

MODE=${1:-default}
PWD=$(pwd)

print_banner() {
  local msg="$1"
  local width=$(( ${#msg} + 4 ))
  local border=$(printf '%*s' "$width" '' | tr ' ' '#')

  echo "$border"
  echo "# $msg #"
  echo "$border"
}

print_usage() {
  cat << EOF
Usage: $0 <command>

Commands:
  setup     Update OS and install dependencies
  update    Build v3xctrl and install the deb package

Examples:
  $0 setup
  $0 update
EOF
}

update_and_install() {
  print_banner "UPDATING OS AND INSTALLING DEPENDENCIES"

  apt update
  apt upgrade -y
  apt install -y lintian mtr minicom screen bc stress-ng
}

install_deb() {
  PKG="$1"
  print_banner "Updating ${PKG}"

  if dpkg -s "$PKG" >/dev/null 2>&1; then
    apt remove -y "$PKG"
  fi
  apt install -y "./build/tmp/${PKG}.deb"
}

# This is used when you want to build and install the deb from your local
# development fork.
build_v3xctrl() {
  print_banner "BUILDING V3XCTRL"

  ./build/build-${NAME}.sh
}

case "$MODE" in
  update)
    build_v3xctrl
    install_deb "${NAME}"
    ;;
  setup)
    update_and_install
    ;;
  *)
    print_usage
    exit 1
  ;;
esac
