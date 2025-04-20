#!/bin/bash
set -e

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root" >&2
  exit 1
fi

USER="v3xctrl"

TMP_DIR="./build/tmp"
MOUNT_DIR="${TMP_DIR}/mnt-image"
DEB_DIR="${TMP_DIR}/dependencies/debs"
IMG="${TMP_DIR}/dependencies/raspios.img.xz"
IMG_WORK="${TMP_DIR}/v3xctrl.img"
INITRD="${TMP_DIR}/initrd.img"

IMG_UNCOMPRESSED="${IMG%.xz}"

MOUNT_BIND_DIRS="dev proc sys"
LOCALE="en_US.UTF-8"


echo "[HOST] Cleanup previous run"
rm -rf "${IMG_UNCOMPRESSED}"
rm -rf "${IMG_WORK}.xz"

echo "[HOST] Extract image"
xz -dk "${IMG}"
mv "${IMG_UNCOMPRESSED}" "${IMG_WORK}"

echo "[HOST] Expanding root file system"
truncate -s +1G "$IMG_WORK"
parted -s "$IMG_WORK" resizepart 2 100%
LOOP_DEV=$(losetup -fP --show "$IMG_WORK")
e2fsck -fy "${LOOP_DEV}p2"
resize2fs "${LOOP_DEV}p2"
losetup -d "$LOOP_DEV"

echo "[HOST] Adding third partition to prevent root expansion on first boot"
truncate -s +8M "$IMG_WORK"
parted -s "$IMG_WORK" -- mkpart primary ext4 100% 100%

echo "[HOST] Reattaching loop device after partitioning"
losetup -d "$LOOP_DEV" || echo "[WARN  ] Loop device already detached"
LOOP_DEV=$(losetup -fP --show "$IMG_WORK")

echo "[HOST] Formatting /data partition"
mkfs.ext4 "${LOOP_DEV}p3"

echo "[HOST] Checking and mounting partitions"
for i in 1 2 3; do
  [ -b "${LOOP_DEV}p$i" ] || { echo "Partition $i missing on $LOOP_DEV"; exit 1; }
done

mkdir -p "$MOUNT_DIR"
mount "${LOOP_DEV}p2" "$MOUNT_DIR"
mount "${LOOP_DEV}p1" "$MOUNT_DIR/boot"
mkdir -p "$MOUNT_DIR/data"
mount "${LOOP_DEV}p3" "$MOUNT_DIR/data"

echo "[HOST] Creating structure under /data"
mkdir -p "${MOUNT_DIR}/data"/{log,config,recordings}
chmod a+rw "${MOUNT_DIR}/data/recordings"

echo "[HOST] Updating /etc/fstab with /data and tmpfs"
PARTUUID=$(blkid -s PARTUUID -o value "${LOOP_DEV}p3")
tee -a "$MOUNT_DIR/etc/fstab" > /dev/null <<EOF
PARTUUID=${PARTUUID} /data ext4 defaults 0 2
EOF

echo "[HOST] Copying files to boot partition"
cp "./build/firstboot.sh" "$MOUNT_DIR/boot/firstboot.sh"
chmod +x "$MOUNT_DIR/boot/firstboot.sh"

echo "[HOST] Binding system directories"
for d in $MOUNT_BIND_DIRS; do
  mount --bind /$d "$MOUNT_DIR/$d"
done

echo "[HOST] Mounting devpts for apt logging and pseudo-terminals"
mount -t devpts devpts "$MOUNT_DIR/dev/pts"

echo "[HOST] Copying qemu-aarch64-static for chroot emulation"
cp /usr/bin/qemu-aarch64-static "$MOUNT_DIR/usr/bin/"

echo "[HOST] Copying .deb files into image"
cp "$DEB_DIR"/*.deb "$MOUNT_DIR/tmp/"

echo "[HOST] Entering chroot to install packages and configure serial login"
cp "./build/chroot/customize-image.sh" "${MOUNT_DIR}"
chmod +x "${MOUNT_DIR}/customize-image.sh"
chroot "$MOUNT_DIR" "/customize-image.sh"
rm "${MOUNT_DIR}/customize-image.sh"

echo "[HOST] Linking /var/log to /data/log"
rm -rf "$MOUNT_DIR/var/log"
ln -s /data/log "$MOUNT_DIR/var/log"

echo "[HOST] Move config files to persistent storage"
if [ -f "$MOUNT_DIR/etc/v3xctrl/config.json" ]; then
    mv "$MOUNT_DIR/etc/v3xctrl/config.json" "$MOUNT_DIR/data/config/config.json"
    ln -sf /data/config/config.json "$MOUNT_DIR/etc/v3xctrl/config.json"
fi

echo "[HOST] Setting enable_uart=1 in config.txt"
if grep -q '^#*enable_uart=' "$MOUNT_DIR/boot/config.txt"; then
  sed -i 's/^#*enable_uart=.*/enable_uart=1/' "$MOUNT_DIR/boot/config.txt"
else
  echo "enable_uart=1" | tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null
fi

#echo "[HOST] Adding console=serial0,115200 before console=tty1 in cmdline.txt"
#sed -i 's/console=tty1/console=serial0,115200 console=tty1/' "$MOUNT_DIR/boot/cmdline.txt"

if ! grep -q 'fsck.repair=yes' "$MOUNT_DIR/boot/cmdline.txt"; then
  echo "[HOST] Appending fsck.repair=yes to cmdline.txt"
  sed -i 's/$/ fsck.repair=yes/' "$MOUNT_DIR/boot/cmdline.txt"
fi

if grep -qw 'quiet' "$MOUNT_DIR/boot/cmdline.txt"; then
  echo "[HOST] Removing 'quiet' from cmdline.txt"
  sed -i 's/\bquiet\b//g' "$MOUNT_DIR/boot/cmdline.txt"
fi

echo "[HOST] Cleaning up and unmounting"
umount "$MOUNT_DIR/boot"
umount "$MOUNT_DIR/data"
umount "$MOUNT_DIR/dev/pts"
for d in $MOUNT_BIND_DIRS; do
  umount "$MOUNT_DIR/$d"
done
umount "$MOUNT_DIR"
losetup -d "$LOOP_DEV"

echo "[HOST] Compressing modified image"
xz -T0 -f "$IMG_WORK"

echo "[HOST] Done — flashable image: ${IMG_WORK}.xz"
