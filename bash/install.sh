
#! /bin/bash

update_and_install() {
  apt update && apt upgrade -y
  apt install -y \
    git libssl-dev libbz2-dev libsqlite3-dev tcpdump liblzma-dev libreadline-dev \
    libctypes-ocaml-dev libcurses-ocaml-dev libffi-dev mtr screen lintian
}

set_swap_size() {
  local SWAP_SIZE="$1"
  local SWAP_PATH="/etc/dphys-swapfile"
  dphys-swapfile swapoff
  sed -i \
    -e "s/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=${SWAPSIZE}/" \
    -e "s/^CONF_MAXSWAP=.*/CONF_MAXSWAP=${SWAPSIZE}/" \
    $SWAP_PATH
  dphys-swapfile setup
  dphys-swapfile swapon
}

install_python() {
  local VERSION="$1"
  local PYENV_PATH="/usr/local/pyenv"
  if [ ! -d $PYENV_PATH ]; then
    git clone https://github.com/pyenv/pyenv.git $PYENV_PATH

    cp ./configs/etc/profile.d/pyenv.sh /etc/profile.d/pyenv.sh
    source /etc/profile.d/pyenv.sh

    pyenv install $VERSION
    pyenv global $VERSION

    chmod -R a+rX $PYENV_PATH
    chmod -R a+w $PYENV_PATH/shims
    chmod -R a+w $PYENV_PATH/versions
  fi
}

update_and_install
set_swap_size 8192
install_python "3.11.4"
