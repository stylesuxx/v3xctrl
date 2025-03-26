#! /bin/bash
# Command is expected to run from within the bash dir - functions are expected
# to return to this folder after they finish.
set -e

MODE=${1:-default}

PWD=$(pwd)
RC_PYTHON_URL="https://github.com/stylesuxx/rc-stream/releases/latest/rc-python.deb"
DOWNLOAD_PATH="${PWD}/dependencies"

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

  sudo apt update && apt upgrade -y
  sudo apt install -y git mtr screen
}

install_python() {
  if ! dpkg -s rc-python >/dev/null 2>&1; then
    mkdir -p $DOWNLOAD_PATH
    cd $DOWNLOAD_PATH
    curl -O $RC_PYTHON_URL
    sudo apt install -y ./rc-python.deb
    cd $PWD
  fi

  sudo update-alternatives --set python /usr/bin/python3.11
  python --version
}

build_and_install() {
  print_banner "BUILDING AND INSTALLING DEB"

  cd "../build"
  ./build-rc-client.sh
  sudo apt reinstall -y ./tmp/rc-client.deb

  # Install python dependencies
  cd "${PWD}"
  sudo pip install -r ../requirements-client.txt

  sudo systemctl restart rc-config-server

  sleep 3
  if systemctl is-active --quiet rc-config-server; then
    echo "Service is running!"
  else
    echo "Service is NOT running, use 'journalctl -u rc-config-server'"
  fi

  cd "${PWD}"
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
    echo "Potential Modem found: $iface"
  else
    echo "No 4g modem found - make sure it is plugged in and shows up via 'ip -c a'"
  fi
}

link_src_dir() {
  TARGET_LINK="/usr/share/rc-client/git-src"

  if [ ! -d $TARGET_LINK ]; then
    cd ..
    SRC_DIR=$(pwd)
    cd ./build

    sudo ln -s "$SRC_DIR" "$TARGET_LINK"
  fi
}

optimize() {
  # Disable IPV6
  echo "net.ipv6.conf.all.disable_ipv6 = 1" | sudo tee -a /etc/sysctl.conf
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
    link_src_dir
    optimize
    check_for_modem
    ;;
esac
