#!/bin/bash
set -e

IMG="$1"
DEB_DIR="$2"
MOUNT_DIR="mnt"
NAME="v3xctrl"

echo "[*] Setting up loop device for $IMG"
LOOP_DEV=$(sudo losetup -fP --show "$IMG")

echo "[*] Mounting root partition"
sudo mkdir -p "$MOUNT_DIR"
sudo mount "${LOOP_DEV}p2" "$MOUNT_DIR"

echo "[*] Binding system directories"
for d in dev proc sys; do
  sudo mount --bind /$d "$MOUNT_DIR/$d"
done

echo "[*] Copying qemu-aarch64-static for chroot emulation"
sudo cp /usr/bin/qemu-aarch64-static "$MOUNT_DIR/usr/bin/"

echo "[*] Copying .deb files"
sudo cp "$DEB_DIR"/*.deb "$MOUNT_DIR/tmp/"

echo "[*] Installing packages inside chroot"
sudo chroot "$MOUNT_DIR" /bin/bash -c "
  apt-get update
  dpkg -i /tmp/*.deb || apt-get install -f -y
  rm /tmp/*.deb
  apt-get clean
"

echo "[*] Cleaning up"
for d in dev proc sys; do
  sudo umount "$MOUNT_DIR/$d"
done
sudo umount "$MOUNT_DIR"
sudo losetup -d "$LOOP_DEV"

echo "[*] Saving modified image"
cp "$IMG" image/v3xctrl-raspios.img
