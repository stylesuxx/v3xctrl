#! /bin/bash
# Command is expected to run from within the bash dir - functions are expected
# to return to this folder after they finish.

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

  apt update && apt upgrade -y
  apt install -y \
    git libssl-dev libbz2-dev libsqlite3-dev tcpdump liblzma-dev libreadline-dev \
    libctypes-ocaml-dev libcurses-ocaml-dev libffi-dev mtr screen lintian
}

set_swap_size() {
  print_banner "INCREASE SWAP SIZE"

  local SWAP_SIZE="$1"
  local SWAP_PATH="/etc/dphys-swapfile"
  dphys-swapfile swapoff
  sed -i \
    -e "s/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=${SWAP_SIZE}/" \
    -e "s/^#CONF_MAXSWAP=.*/CONF_MAXSWAP=${SWAP_SIZE}/" \
    $SWAP_PATH
  dphys-swapfile setup
  dphys-swapfile swapon
}

install_python() {
  print_banner "INSTALLING PYTHON SYSTEM WIDE VIA PYENV"

  local VERSION="$1"
  local PYENV_PATH="/usr/local/pyenv"
  if [ ! -d $PYENV_PATH ]; then
    git clone https://github.com/pyenv/pyenv.git $PYENV_PATH

    cp ./configs/etc/profile.d/pyenv.sh /etc/profile.d/pyenv.sh
    . /etc/profile.d/pyenv.sh

    pyenv install $VERSION
    pyenv global $VERSION

    chmod -R a+rX $PYENV_PATH
    chmod -R a+w $PYENV_PATH/shims
    chmod -R a+w $PYENV_PATH/versions
  else
    . /etc/profile.d/pyenv.sh
  fi

  python --version
  /usr/local/pyenv/versions/${VERSION}/bin/pip install -r ../requirements.txt
}

build_and_install() {
  print_banner "BUILDING AND INSTALLING DEB"

  cd ../build
  ./build.sh
  apt install -y ./tmp/rc-client.deb
  systemctl start rc-config-server

  sleep 3
  if systemctl is-active --quiet rc-config-server; then
    echo "Service is running!"
  else
    echo "Service is NOT running, use 'journalctl -u rc-config-server'"
  fi

  cd ../bash
}

fix_locale() {
  print_banner "FIXING LOCALE"

  local LOCALE="en_US.UTF-8"
  sed -i "s/^# *$LOCALE UTF-8/$LOCALE UTF-8/" /etc/locale.gen
  locale-gen
  update-locale LANG=$LOCALE
}

check_for_modem() {
  local IFACE=$(ip -o link show | awk -F': ' '{print $2}' | grep -vE '^(lo|wlan0)$' | head -n1)

  if [ -n "$IFACE" ]; then
    echo "Potential Modem foun: $iface"
  else
    echo "No 4g modem found - make sure it is plugged in and shows up via 'ip -c a'"
  fi
}

link_src_dir() {
  TARGET_LINK="/usr/share/rc-client/git-src"

  cd ..
  SRC_DIR=$(pwd)
  cd ./build

  ln -s "$SRC_DIR" "$TARGET_LINK"
}

fix_locale
update_and_install
set_swap_size 8192
install_python "3.11.4"
build_and_install
check_for_modem
link_src_dir
