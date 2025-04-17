#!/bin/bash
set -e

MOUNT_DIR="$1"
IMG="$2"
DEB_DIR="$3"
IMG_DESTINATION="$4"

IMG_UNCOMPRESSED="${IMG%.xz}"
IMG_WORK="v3xctrl.img"

MOUNT_BIND_DIRS="dev proc sys"
LOCALE="en_US.UTF-8"

echo "[HOST  ] Installing dependencies"
sudo apt-get update
sudo apt-get install -y parted e2fsprogs qemu-user-static binfmt-support \
  kpartx dosfstools debootstrap xz-utils

echo "[HOST  ] Cleanup previous run"
rm -rf "${IMG_UNCOMPRESSED}"
rm -rf "${IMG_DESTINATION}"

echo "[HOST  ] Extract image"
xz -dk "${IMG}"
mv "${IMG_UNCOMPRESSED}" "${IMG_WORK}"

echo "[HOST  ] Expanding root file system"
truncate -s +1G "$IMG_WORK"
sudo parted -s "$IMG_WORK" resizepart 2 100%
LOOP_DEV=$(sudo losetup -fP --show "$IMG_WORK")
sudo e2fsck -fy "${LOOP_DEV}p2"
sudo resize2fs "${LOOP_DEV}p2"

sudo losetup -d "$LOOP_DEV"

echo "[HOST  ] Growing image minimally for placeholder partition"
truncate -s +8M "$IMG_WORK"

echo "[HOST  ] Adding third partition to prevent root expansion on first boot"
sudo parted -s "$IMG_WORK" -- mkpart primary ext4 100% 100%

echo "[HOST  ] Setting up loop device for $IMG_WORK"
LOOP_DEV=$(sudo losetup -fP --show "$IMG_WORK")

echo "[HOST  ] Mounting root partition"
sudo mkdir -p "$MOUNT_DIR"
sudo mount "${LOOP_DEV}p2" "$MOUNT_DIR"

echo "[HOST  ] Mounting boot partition (FAT32)"
sudo mount "${LOOP_DEV}p1" "$MOUNT_DIR/boot"

echo "[HOST  ] Injecting custom.toml to trigger rc-create-data-partition on first boot"
sudo tee "$MOUNT_DIR/boot/custom.toml" > /dev/null <<EOF
[run]
script = "/usr/bin/rc-firstboot"
EOF

#echo "[HOST  ] Removing init_resize.sh trigger from cmdline.txt"
#sudo sed -i 's|\s*init=/usr/lib/raspi-config/init_resize.sh||' "$MOUNT_DIR/boot/cmdline.txt"

echo "[HOST  ] Binding system directories"
for d in $MOUNT_BIND_DIRS; do
  sudo mount --bind /$d "$MOUNT_DIR/$d"
done

echo "[HOST  ] Mounting devpts for apt logging and pseudo-terminals"
sudo mount -t devpts devpts "$MOUNT_DIR/dev/pts"

echo "[HOST  ] Copying qemu-aarch64-static for chroot emulation"
sudo cp /usr/bin/qemu-aarch64-static "$MOUNT_DIR/usr/bin/"

echo "[HOST  ] Copying .deb files into image"
sudo cp "$DEB_DIR"/*.deb "$MOUNT_DIR/tmp/"

echo "[HOST  ] Entering chroot to install packages and configure serial login"
sudo chroot "$MOUNT_DIR" /bin/bash -c "
  set -e
  export DEBIAN_FRONTEND=noninteractive

  echo '[CHROOT] Fixing locale'
  sed -i 's/^# *$LOCALE UTF-8/$LOCALE UTF-8/' /etc/locale.gen
  locale-gen
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
"

echo "[HOST  ] Setting enable_uart=1 in config.txt"
if grep -q '^#*enable_uart=' "$MOUNT_DIR/boot/config.txt"; then
  sudo sed -i 's/^#*enable_uart=.*/enable_uart=1/' "$MOUNT_DIR/boot/config.txt"
else
  echo "enable_uart=1" | sudo tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null
fi

echo "[HOST  ] Adding console=serial0,115200 before console=tty1 in cmdline.txt"
sudo sed -i 's/console=tty1/console=serial0,115200 console=tty1/' "$MOUNT_DIR/boot/cmdline.txt"

if ! grep -q 'fsck.repair=yes' "$MOUNT_DIR/boot/cmdline.txt"; then
  echo "[HOST  ] Appending fsck.repair=yes to cmdline.txt"
  sudo sed -i 's/$/ fsck.repair=yes/' "$MOUNT_DIR/boot/cmdline.txt"
fi

if grep -qw 'quiet' "$MOUNT_DIR/boot/cmdline.txt"; then
  echo "[HOST  ] Removing 'quiet' from cmdline.txt"
  sudo sed -i 's/\bquiet\b//g' "$MOUNT_DIR/boot/cmdline.txt"
fi

echo "[HOST  ] Cleaning up and unmounting"
sudo umount "$MOUNT_DIR/boot"
sudo umount "$MOUNT_DIR/dev/pts"
for d in $MOUNT_BIND_DIRS; do
  sudo umount "$MOUNT_DIR/$d"
done
sudo umount "$MOUNT_DIR"
sudo losetup -d "$LOOP_DEV"

echo "[HOST  ] Compressing modified image"
xz -T0 -f "$IMG_WORK"

echo "[HOST  ] Moving compressed image to output"
mv "$IMG_WORK.xz" ${IMG_DESTINATION}

echo "[HOST  ] Done — flashable image: ${IMG_DESTINATION}"
