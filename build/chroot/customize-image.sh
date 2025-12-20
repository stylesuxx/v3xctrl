#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

USER="v3xctrl"
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

echo '[CHROOT] Enabling firstboot service...'
systemctl enable v3xctrl-firstboot.service

echo '[CHROOT] Setting up Samba...'
usermod -s /bin/bash "${USER}"
echo -e "${USER}\n${USER}" | smbpasswd -a -s "${USER}"
smbpasswd -e "${USER}"
systemctl disable smbd

echo '[CHROOT] Setting default hostname...'
echo "v3xctrl" > /etc/hostname
sed -i 's/127.0.1.1.*/127.0.1.1\tv3xctrl/' /etc/hosts

echo '[CHROOT] Fixing file permissions'
chown -R $USER:$USER '/data/recordings'
