#! /bin/bash
# Command is expected to be run from the root of the project diretory.
set -e

MODE=${1:-default}

PWD=$(pwd)
RC_PYTHON_URL="https://github.com/stylesuxx/rc-stream/releases/latest/rc-python.deb"
DOWNLOAD_PATH="${PWD}/build/dependencies"

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

  sudo apt update && sudo apt upgrade -y
  sudo apt install -y git mtr screen lintian
}

install_python() {
  if ! dpkg -s rc-python >/dev/null 2>&1; then
    mkdir -p $DOWNLOAD_PATH
    cd $DOWNLOAD_PATH
    curl -O $RC_PYTHON_URL
    sudo apt install -y "${PWD}/build/tmp/rc-python.deb"
  fi

  # Print versions to make sure everything is in place and working
  rc-python --version
  rc-pip --version
}

# This is used when you want to build and install the deb from your local
# development fork.
build_and_install() {
  print_banner "BUILDING AND INSTALLING DEB"
  PKG="v3xctrl"

  sudo ./build/build-${PKG}.sh

  if dpkg -s "$PKG" >/dev/null 2>&1; then
    sudo apt remove -y "$PKG"
  fi
  sudo apt install -y "./build/tmp/${PKG}.deb"

  # Install python dependencies
  # sudo rc-pip install -r ./requirements-client.txt
}

fix_locale() {
  print_banner "FIXING LOCALE"

  local LOCALE="en_US.UTF-8"
  sudo sed -i "s/^# *$LOCALE UTF-8/$LOCALE UTF-8/" /etc/locale.gen
  sudo locale-gen
  sudo update-locale LANG=$LOCALE
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
  update)
    build_and_install
    ;;
  *)
    fix_locale
    install_python
    update_and_install
    build_and_install
    check_for_modem
    ;;
esac
