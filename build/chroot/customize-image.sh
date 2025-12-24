#!/bin/bash
# Keep things to be done in chroot to a minimum, preferably do all modifications
# in the host system - this is more performant.
set -e
export DEBIAN_FRONTEND=noninteractive

USER="v3xctrl"
NAME="v3xctrl"
LOCALE="en_US.UTF-8"

echo '[CHROOT] Fetching signed regulatory domain files'
curl -L https://kernel.googlesource.com/pub/scm/linux/kernel/git/sforshee/wireless-regdb/+/refs/heads/master/regulatory.db\?format=TEXT | base64 -d | tee /lib/firmware/regulatory.db > /dev/null
curl -L https://kernel.googlesource.com/pub/scm/linux/kernel/git/sforshee/wireless-regdb/+/refs/heads/master/regulatory.db.p7s\?format=TEXT | base64 -d | tee /lib/firmware/regulatory.db.p7s > /dev/null

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

echo '[CHROOT] Installing dependencies...'
apt-get install -y /tmp/*.deb

echo '[CHROOT] Removing bloat...'
rm -f /tmp/*.deb
apt-get autoremove -y
apt-get clean

# Samba username is password
echo '[CHROOT] Setting up Samba...'
usermod -s /bin/bash "${USER}"
echo -e "${USER}\n${USER}" | smbpasswd -a -s "${USER}"
smbpasswd -e "${USER}"
systemctl disable smbd

# This needs to be done here since we need the user reference in order to change
# file permissions.
echo "[CHROOT] Copying config files to persistent storage..."
if [ -f "/etc/$NAME/config.json" ]; then
  cp "/etc/$NAME/config.json" "/data/config/config.json"
  chown $USER:$USER "/data/config/config.json"
  chmod a+r "/data/config/config.json"
fi

echo '[CHROOT] Fixing file permissions'
chown -R $USER:$USER '/data/recordings'

echo '[CHROOT] Enabling firstboot service...'
systemctl enable v3xctrl-firstboot.service
