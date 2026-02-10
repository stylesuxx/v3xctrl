#!/bin/bash
# Keep things to be done in chroot to a minimum, preferably do all modifications
# in the host system - this is more performant.
set -e
export DEBIAN_FRONTEND=noninteractive

# Parse flags
USE_LOCAL_DEBS=false
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --local|-l) USE_LOCAL_DEBS=true ;;
  esac
  shift
done

USER="v3xctrl"
NAME="v3xctrl"
LOCALE="en_US.UTF-8"

echo '[CHROOT] Fetching signed regulatory domain files'
curl -L https://kernel.googlesource.com/pub/scm/linux/kernel/git/sforshee/wireless-regdb/+/refs/heads/master/regulatory.db\?format=TEXT | base64 -d | tee /lib/firmware/regulatory.db > /dev/null
curl -L https://kernel.googlesource.com/pub/scm/linux/kernel/git/sforshee/wireless-regdb/+/refs/heads/master/regulatory.db.p7s\?format=TEXT | base64 -d | tee /lib/firmware/regulatory.db.p7s > /dev/null

if [ "$USE_LOCAL_DEBS" = false ]; then
  echo '[CHROOT] Adding V3XCTRL repository...'
  curl -fsSL https://repo.v3xctrl.com/public.key | gpg --dearmor -o /usr/share/keyrings/v3xctrl.gpg
  echo "deb [signed-by=/usr/share/keyrings/v3xctrl.gpg arch=arm64] https://repo.v3xctrl.com trixie main" > /etc/apt/sources.list.d/v3xctrl.list
fi

echo '[CHROOT] Updating system...'
apt-get update
apt-get upgrade -y

echo '[CHROOT] Installing nice to haves...'
apt-get install -y \
  locales-all \
  git \
  iperf3 \
  minicom \
  mtr \
  nload

echo '[CHROOT] Fixing locale'
locale-gen $LOCALE
update-locale LANG="$LOCALE"

echo '[CHROOT] Installing V3XCTRL packages...'
if [ "$USE_LOCAL_DEBS" = true ]; then
  apt-get install -y /tmp/*.deb
  rm -f /tmp/*.deb
else
  apt-get install -y v3xctrl
fi

echo '[CHROOT] Removing bloat...'
apt-get autoremove -y
apt-get clean

# Samba username is password
echo '[CHROOT] Setting up Samba...'
usermod -s /bin/bash "${USER}"
echo -e "${USER}\n${USER}" | smbpasswd -a -s "${USER}"
smbpasswd -e "${USER}"
systemctl disable smbd

# Set permissions on /data directories
echo '[CHROOT] Fixing file permissions'
chown -R $USER:$USER '/data/recordings'
chown -R $USER:$USER '/data/config'
chmod 640 /data/config/config.json

echo '[CHROOT] Enabling firstboot service...'
systemctl enable v3xctrl-firstboot.service
