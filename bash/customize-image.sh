#!/bin/bash
set -e

IMG="$1"
DEB_DIR="$2"
MOUNT_DIR="mnt"

echo "[*] Setting up loop device for $IMG"
LOOP_DEV=$(sudo losetup -fP --show "$IMG")

echo "[*] Mounting root partition"
sudo mkdir -p "$MOUNT_DIR"
sudo mount "${LOOP_DEV}p2" "$MOUNT_DIR"

echo "[*] Mounting boot partition (FAT32)"
# This is required for editing config.txt and cmdline.txt
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

echo "[*] Entering chroot to install packages and enable serial console"
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

  echo '[*] Enabling serial console login...'
  systemctl enable serial-getty@serial0.service
"

echo "[*] Enabling UART in config.txt"
echo "enable_uart=1" | sudo tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null

echo "[*] Enabling kernel console output in cmdline.txt"
sudo sed -i 's/\brootwait\b/rootwait console=serial0,115200/' "$MOUNT_DIR/boot/cmdline.txt"

echo "[*] Cleaning up and unmounting"
sudo umount "$MOUNT_DIR/boot"
sudo umount "$MOUNT_DIR/dev/pts"
for d in dev proc sys; do
  sudo umount "$MOUNT_DIR/$d"
done
sudo umount "$MOUNT_DIR"
sudo losetup -d "$LOOP_DEV"

echo "[*] Compressing modified image"
xz -T0 -f "$IMG"

echo "[*] Moving compressed image to output"
mv "$IMG.xz" image/v3xctrl-raspios.img.xz

echo "[*] Done — flashable image: image/v3xctrl-raspios.img.xz"
