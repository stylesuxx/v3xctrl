#!/bin/bash
set -e

MOUNT_DIR="$1"
IMG="$2"
DEB_DIR="$3"
IMG_DESTINATION="$4"

IMG_UNCOMPRESSED="${IMG%.xz}"

echo "[*] Installing dependencies"
sudo apt-get update
sudo apt-get install -y parted e2fsprogs qemu-user-static binfmt-support \
  kpartx dosfstools debootstrap xz-utils

echo "[*] Cleanup previous run"
rm -rf "${IMG_UNCOMPRESSED}"
rm -rf "${IMG_DESTINATION}"

echo "[*] Extract image"
xz -dk "${IMG}"

echo "[*] Expanding root file system"
# Grow image file by 1G
truncate -s +1G "$IMG_UNCOMPRESSED"

# Tell parted to script without prompts and expand partition 2
sudo parted -s "$IMG_UNCOMPRESSED" resizepart 2 100%

# Setup loop device
LOOP_DEV=$(sudo losetup -fP --show "$IMG_UNCOMPRESSED")

# Run e2fsck non-interactively
sudo e2fsck -fy "${LOOP_DEV}p2"

# Resize filesystem to fill partition
sudo resize2fs "${LOOP_DEV}p2"
sudo losetup -d "$LOOP_DEV"

echo "[*] Setting up loop device for $IMG_UNCOMPRESSED"
LOOP_DEV=$(sudo losetup -fP --show "$IMG_UNCOMPRESSED")

echo "[*] Mounting root partition"
sudo mkdir -p "$MOUNT_DIR"
sudo mount "${LOOP_DEV}p2" "$MOUNT_DIR"

echo "[*] Mounting boot partition (FAT32)"
sudo mount "${LOOP_DEV}p1" "$MOUNT_DIR/boot"

echo "[*] Binding system directories"
for d in dev proc sys; do
  sudo mount --bind /$d "$MOUNT_DIR/$d"
done

echo "[*] Mounting devpts for apt logging and pseudo-terminals"
sudo mount -t devpts devpts "$MOUNT_DIR/dev/pts"

echo "[*] Copying qemu-aarch64-static for chroot emulation"
sudo cp /usr/bin/qemu-aarch64-static "$MOUNT_DIR/usr/bin/"

echo "[*] Copying .deb files into image"
sudo cp "$DEB_DIR"/*.deb "$MOUNT_DIR/tmp/"

echo "[*] Entering chroot to install packages and configure serial login"
sudo chroot "$MOUNT_DIR" /bin/bash -c "
  set -e
  export DEBIAN_FRONTEND=noninteractive

  echo '[*] Disabling libc-bin postinst to avoid qemu segfault...'
  if [ -f /var/lib/dpkg/info/libc-bin.postinst ]; then
    mv /var/lib/dpkg/info/libc-bin.postinst /var/lib/dpkg/info/libc-bin.postinst.bak
    echo '#!/bin/sh' > /var/lib/dpkg/info/libc-bin.postinst
    chmod +x /var/lib/dpkg/info/libc-bin.postinst
  fi

  echo '[*] Installing .deb packages...'
  apt-get update
  apt install -y /tmp/*.deb || true
  dpkg --configure -a || true

  echo '[*] Restoring libc-bin postinst...'
  if [ -f /var/lib/dpkg/info/libc-bin.postinst.bak ]; then
    mv /var/lib/dpkg/info/libc-bin.postinst.bak /var/lib/dpkg/info/libc-bin.postinst
  fi

  rm -f /tmp/*.deb
  apt-get clean
"

echo "[*] Setting enable_uart=1 in config.txt"
if grep -q '^#*enable_uart=' "$MOUNT_DIR/boot/config.txt"; then
  sudo sed -i 's/^#*enable_uart=.*/enable_uart=1/' "$MOUNT_DIR/boot/config.txt"
else
  echo "enable_uart=1" | sudo tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null
fi

echo "[*] Adding console=serial0,115200 before console=tty1 in cmdline.txt"
sudo sed -i 's/console=tty1/console=serial0,115200 console=tty1/' "$MOUNT_DIR/boot/cmdline.txt"

if ! grep -q 'fsck.repair=yes' "$MOUNT_DIR/boot/cmdline.txt"; then
  echo "[*] Appending fsck.repair=yes to cmdline.txt"
  sudo sed -i 's/$/ fsck.repair=yes/' "$MOUNT_DIR/boot/cmdline.txt"
fi

echo "[*] Cleaning up and unmounting"
sudo umount "$MOUNT_DIR/boot"
sudo umount "$MOUNT_DIR/dev/pts"
for d in dev proc sys; do
  sudo umount "$MOUNT_DIR/$d"
done
sudo umount "$MOUNT_DIR"
sudo losetup -d "$LOOP_DEV"

echo "[*] Compressing modified image"
xz -T0 -f "$IMG_UNCOMPRESSED"

echo "[*] Moving compressed image to output"
mv "$IMG_UNCOMPRESSED.xz" ${IMG_DESTINATION}

echo "[*] Done — flashable image: ${IMG_DESTINATION}"
