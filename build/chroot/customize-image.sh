#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

USER="v3xctrl"
LOCALE="en_US.UTF-8"

echo '[CHROOT] Fixing locale'
echo "$LOCALE UTF-8" >> /etc/locale.gen
locale-gen
echo "LANG=$LOCALE" > /etc/default/locale
update-locale LANG=$LOCALE

echo '[CHROOT] Disabling libc-bin postinst to avoid qemu segfault...'
if [ -f /var/lib/dpkg/info/libc-bin.postinst ]; then
  mv /var/lib/dpkg/info/libc-bin.postinst /var/lib/dpkg/info/libc-bin.postinst.bak
  echo '#!/bin/sh' > /var/lib/dpkg/info/libc-bin.postinst
  chmod +x /var/lib/dpkg/info/libc-bin.postinst
fi

echo '[CHROOT] Installing .deb packages...'
apt-get update
apt install -y /tmp/*.deb || true
dpkg --configure -a || true

rm -f /tmp/*.deb
apt-get clean

echo '[CHROOT] Restoring libc-bin postinst...'
if [ -f /var/lib/dpkg/info/libc-bin.postinst.bak ]; then
  mv /var/lib/dpkg/info/libc-bin.postinst.bak /var/lib/dpkg/info/libc-bin.postinst
fi

echo '[CHROOT] Building initrd.img for overlayfs...'
raspi-config nonint enable_overlayfs
sed -i 's/\bboot=overlay\b//' "/boot/cmdline.txt"

chown $USER:$USER '/data/recordings'
