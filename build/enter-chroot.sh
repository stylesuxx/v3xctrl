#!/bin/bash
set -e

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root" >&2
  exit 1
fi

TMP_DIR="./build/tmp"
MOUNT_DIR="${TMP_DIR}/mnt-build"
IMG_WORK="${TMP_DIR}/v3xctrl-build.img"
IMG="${TMP_DIR}/dependencies/raspios.img.xz"
IMG_UNCOMPRESSED="${IMG%.xz}"
MOUNT_BIND_DIRS="dev proc sys"
LOOP_STATE_FILE="${TMP_DIR}/.loop_device"

if [ ! -f "${IMG_WORK}" ]; then
  echo "[HOST] Extract image"
  xz -dk "${IMG}"
  mv "${IMG_UNCOMPRESSED}" "${IMG_WORK}"

  echo "[HOST] Expanding root file system"
  truncate -s +5G "$IMG_WORK"
  parted -s "$IMG_WORK" resizepart 2 100%
  LOOP_DEV=$(losetup -fP --show "$IMG_WORK")
  e2fsck -fy "${LOOP_DEV}p2"
  resize2fs "${LOOP_DEV}p2"
else
  LOOP_DEV=$(losetup -fP --show "$IMG_WORK")
fi

# Save loop device for exit script
echo "$LOOP_DEV" > "$LOOP_STATE_FILE"

partprobe "$LOOP_DEV"
sleep 1

echo "[HOST] Checking and mounting partitions"
for i in 1 2; do
  [ -b "${LOOP_DEV}p$i" ] || { echo "Partition $i missing on $LOOP_DEV"; exit 1; }
done

mkdir -p "$MOUNT_DIR"
mount "${LOOP_DEV}p2" "$MOUNT_DIR"
mount "${LOOP_DEV}p1" "$MOUNT_DIR/boot"

echo "[HOST] Binding system directories"
for d in $MOUNT_BIND_DIRS; do
  mount --bind /$d "$MOUNT_DIR/$d"
done

echo "[HOST] Mounting devpts for apt logging and pseudo-terminals"
mount -t devpts devpts "$MOUNT_DIR/dev/pts"

echo "[HOST] Copying qemu-aarch64-static for chroot emulation"
cp /usr/bin/qemu-aarch64-static "$MOUNT_DIR/usr/bin/"

echo "[HOST] Entering chroot (type 'exit' to leave)"
chroot "$MOUNT_DIR" /bin/bash
