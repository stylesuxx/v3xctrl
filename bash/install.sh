#! /bin/bash
# Command is expected to be run from the root of the project diretory.
# This script is meant for easy package rebuild and install during development.
set -e

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

update_and_install() {
  print_banner "UPDATING OS AND INSTALLING DEPENDENCIES"

  sudo apt update
  sudo apt upgrade -y
  sudo apt install -y mtr minicom screen lintian bc stress-ng
}

build_python() {
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

  sudo apt update
  sudo apt install -y build-essential libssl-dev libbz2-dev libsqlite3-dev \
    liblzma-dev libreadline-dev libctypes-ocaml-dev libcurses-ocaml-dev \
    libffi-dev

  sudo ./build/build-python.sh
}

install_deb() {
  PKG="$1"
  print_banner "INSTALLING ${PKG}"

  if dpkg -s "$PKG" >/dev/null 2>&1; then
    sudo apt remove -y "$PKG"
  fi
  sudo apt install -y "./build/tmp/${PKG}.deb"
}

# This is used when you want to build and install the deb from your local
# development fork.
build_v3xctrl() {
  print_banner "BUILDING V3XCTRL"
  PKG="v3xctrl"

  sudo ./build/build-${PKG}.sh
}

check_for_modem() {
  local IFACE=$(ip -o link show | awk -F': ' '{print $2}' | grep -vE '^(lo|wlan0)$' | head -n1)

  if [ -n "$IFACE" ]; then
    echo "Potential Modem found: $IFACE"
  else
    echo "No 4g modem found - make sure it is plugged in and shows up via 'ip -c a'"
  fi
}

case "$MODE" in
  python)
    build_python
    install_deb v3xctrl-python

    # Print versions to make sure everything is in place and working
    v3xctrl-python --version
    v3xctrl-pip --version
    ;;
  update)
    build_v3xctrl
    install_deb v3xctrl
    ;;
  *)
    update_and_install
    check_for_modem
    ;;
esac
