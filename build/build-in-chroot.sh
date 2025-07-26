#!/bin/bash
set -e

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root" >&2
  exit 1
fi

TMP_DIR="./build/tmp"
PACKAGES_DIR="build/packages"
MOUNT_DIR="${TMP_DIR}/mnt-build"
IMG_WORK="${TMP_DIR}/v3xctrl-build.img"
IMG="${TMP_DIR}/dependencies/raspios.img.xz"
DEB_PATH="${TMP_DIR}/dependencies/debs"
IMG_UNCOMPRESSED="${IMG%.xz}"
MOUNT_BIND_DIRS="dev proc sys"

cleanup() {
  echo "[HOST] Cleaning up and unmounting"
  umount -lf "$MOUNT_DIR/boot" 2>/dev/null || true
  umount -lf "$MOUNT_DIR/dev/pts" 2>/dev/null || true
  for d in $MOUNT_BIND_DIRS; do
    umount -lf "$MOUNT_DIR/$d" 2>/dev/null || true
  done
  umount -lf "$MOUNT_DIR" 2>/dev/null || true
  losetup -d "$LOOP_DEV" 2>/dev/null || true
}
trap cleanup EXIT

if [ ! -f "${IMG_WORK}" ]; then
  echo "[HOST] Extract image"
  xz -dk "${IMG}"
  mv "${IMG_UNCOMPRESSED}" "${IMG_WORK}"

  echo "[HOST  ] Expanding root file system"
  truncate -s +5G "$IMG_WORK"
  parted -s "$IMG_WORK" resizepart 2 100%
  LOOP_DEV=$(losetup -fP --show "$IMG_WORK")
  e2fsck -fy "${LOOP_DEV}p2"
  resize2fs "${LOOP_DEV}p2"
else
  LOOP_DEV=$(losetup -fP --show "$IMG_WORK")
fi

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

echo "[HOST] Moving build files into place"
rm -rf "${MOUNT_DIR}/src"

mkdir -p "${MOUNT_DIR}/src/${PACKAGES_DIR}"

cp -r "./${PACKAGES_DIR}/v3xctrl-python" "${MOUNT_DIR}/src/${PACKAGES_DIR}"
cp -r "./${PACKAGES_DIR}/v3xctrl" "${MOUNT_DIR}/src/${PACKAGES_DIR}"

cp -r "./build/requirements" "${MOUNT_DIR}/src/build"
cp -r "./build/build-python.sh" "${MOUNT_DIR}/src/build"
cp -r "./build/build-v3xctrl.sh" "${MOUNT_DIR}/src/build"
cp -r "./web-server" "${MOUNT_DIR}/src"
cp -r "./src" "${MOUNT_DIR}/src"
cp "./build/chroot/build-debs.sh" "${MOUNT_DIR}"
chmod +x "${MOUNT_DIR}/build-debs.sh"

echo "[HOST] Entering chroot and starting build"
chroot "$MOUNT_DIR" "./build-debs.sh"
cp ${MOUNT_DIR}/src/build/tmp/*.deb "${DEB_PATH}"
