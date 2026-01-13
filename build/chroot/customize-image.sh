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

# Set permissions on /data directories
echo '[CHROOT] Fixing file permissions'
chown -R $USER:$USER '/data/recordings'
chown -R $USER:$USER '/data/config'
chmod 640 /data/config/config.json

# Enable the bind mount so /etc/v3xctrl points to /data/config
echo '[CHROOT] Enabling etc-v3xctrl.mount for persistent config...'
systemctl enable etc-v3xctrl.mount

echo '[CHROOT] Enabling firstboot service...'
systemctl enable v3xctrl-firstboot.service
