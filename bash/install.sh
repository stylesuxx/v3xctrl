#! /bin/bash
apt update && apt upgrade -y
apt install -y \
  git libssl-dev libbz2-dev libsqlite3-dev tcpdump liblzma-dev libreadline-dev \
  libctypes-ocaml-dev libcurses-ocaml-dev libffi-dev mtr screen lintian

# Increas SWAP size
SWAP_PATH="/etc/dphys-swapfile"
SWAP_SIZE=8192
dphys-swapfile swapoff
sed -i \
  -e "s/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=${SWAPSIZE}/" \
  -e "s/^CONF_MAXSWAP=.*/CONF_MAXSWAP=${SWAPSIZE}/" \
  $SWAP_PATH
dphys-swapfile setup
dphys-swapfile swapon

# Install Python via pyenv
PYENV_PATH="/usr/local/pyenv"
if [ ! -d $PYENV_PATH ]; then
  git clone https://github.com/pyenv/pyenv.git $PYENV_PATH

  cp ./configs/etc/profile.d/pyenv.sh /etc/profile.d/pyenv.sh
  source /etc/profile.d/pyenv.sh

  pyenv install 3.11.4
  pyenv global 3.11.4

  chmod -R a+rX $PYENV_PATH
  chmod -R a+w $PYENV_PATH/shims
  chmod -R a+w $PYENV_PATH/versions
fi
