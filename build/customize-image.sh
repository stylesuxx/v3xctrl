#!/bin/bash
set -e

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root" >&2
  exit 1
fi

# Accept arguments: MOUNT_DIR INPUT_IMG DEB_DIR OUTPUT_IMG
# If not provided, use defaults for local builds
MOUNT_DIR_ARG="${1:-}"
INPUT_IMG="${2:-}"
DEB_DIR_ARG="${3:-}"
OUTPUT_IMG="${4:-}"

USER="v3xctrl"
CONF_DIR="./build/configs"

# Use provided arguments or defaults
if [ -n "$MOUNT_DIR_ARG" ]; then
  MOUNT_DIR="$MOUNT_DIR_ARG"
  IMG="$INPUT_IMG"
  DEB_DIR="$DEB_DIR_ARG"
  IMG_WORK="${OUTPUT_IMG%.xz}"
else
  # Default paths for local builds
  TMP_DIR="./build/tmp"
  MOUNT_DIR="${TMP_DIR}/mnt-image"
  DEB_DIR="${TMP_DIR}/dependencies/debs"
  IMG="${TMP_DIR}/dependencies/raspios.img.xz"
  IMG_WORK="${TMP_DIR}/v3xctrl.img"
  OUTPUT_IMG="${IMG_WORK}.xz"
fi

INITRD="${TMP_DIR:-./build/tmp}/initrd.img"
SSHD_CONFIG="${MOUNT_DIR}/etc/ssh/sshd_config"
MOTD_CONFIG="${MOUNT_DIR}/etc/motd"
JOURNALD_CONF="${MOUNT_DIR}/etc/systemd/journald.conf"

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
truncate -s +2G "$IMG_WORK"
parted -s "$IMG_WORK" resizepart 2 100%
LOOP_DEV=$(losetup -fP --show "$IMG_WORK")
partprobe "$LOOP_DEV"
blockdev --rereadpt "$LOOP_DEV" || true
sleep 5
udevadm settle

# Make sure fs is clean before and after resizing
e2fsck -fy "${LOOP_DEV}p2"
resize2fs "${LOOP_DEV}p2"
e2fsck -fy "${LOOP_DEV}p2"

echo "[HOST] Adding third partition to prevent root expansion on first boot"
losetup -d "$LOOP_DEV"
truncate -s +32MiB "$IMG_WORK"
parted -s "$IMG_WORK" -- mkpart primary ext4 -32MiB 100%
LOOP_DEV=$(losetup -fP --show "$IMG_WORK")
partprobe "$LOOP_DEV"
blockdev --rereadpt "$LOOP_DEV" || true
sleep 5
udevadm settle

echo "[HOST] Verifying partition exists before formatting"
if [ ! -b "${LOOP_DEV}p3" ]; then
  echo "[ERROR] Partition 3 device ${LOOP_DEV}p3 not found after partitioning"
  exit 1
fi

echo "[HOST] Formatting /data partition at full partition size"
mkfs.ext4 -F "${LOOP_DEV}p3"
e2fsck -fy "${LOOP_DEV}p3"

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

echo "[HOST] Binding system directories..."
for d in $MOUNT_BIND_DIRS; do
  mount --bind /$d "$MOUNT_DIR/$d"
done
mount -t devpts devpts "$MOUNT_DIR/dev/pts"

echo "[HOST] Copying qemu-aarch64-static for chroot emulation"
cp /usr/bin/qemu-aarch64-static "$MOUNT_DIR/usr/bin/"

echo "[HOST] Copying .deb files into image"
cp "$DEB_DIR"/v3xctrl-python.deb "$MOUNT_DIR/tmp/"
cp "$DEB_DIR"/v3xctrl.deb "$MOUNT_DIR/tmp/"

### CHROOT START ###
echo "[HOST] Entering chroot to install packages and configure serial login"
cp "./build/chroot/customize-image.sh" "${MOUNT_DIR}"
chmod +x "${MOUNT_DIR}/customize-image.sh"
chroot "$MOUNT_DIR" "/customize-image.sh"
rm "${MOUNT_DIR}/customize-image.sh"
### CHROOT END   ###

echo "[HOST] Adjust SSH welcome message"
if grep -qE '^\s*PrintLastLog' "$SSHD_CONFIG"; then
    sed -i 's/^\s*PrintLastLog.*/PrintLastLog no/' "$SSHD_CONFIG"
else
    echo 'PrintLastLog no' >> "$SSHD_CONFIG"
fi
sed -i 's|^\(session[[:space:]]\+optional[[:space:]]\+pam_motd\.so[[:space:]]\+noupdate\)|#\1|' "${MOUNT_DIR}/etc/pam.d/sshd"

echo "[HOST] Move config files into place"
cp "${CONF_DIR}/smb.conf" "$MOUNT_DIR/etc/samba/smb.conf"
cp "${CONF_DIR}/10_v3xctrl-motd-firstboot.sh" "$MOUNT_DIR/etc/profile.d/"
cp "${CONF_DIR}/97-overlayroot" "$MOUNT_DIR/etc/update-motd.d/97-overlayroot"

echo "[HOST] Copying files to boot partition..."
cp "./build/firstboot.sh" "$MOUNT_DIR/boot/firstboot.sh"
chmod +x "$MOUNT_DIR/boot/firstboot.sh"

echo "[HOST] Updating journald for persistent storage..."
if grep -Eq '^\s*#?\s*Storage=' "$JOURNALD_CONF"; then
  sed -i -E 's|^\s*#?\s*Storage=.*|Storage=persistent|' "$JOURNALD_CONF"
fi

echo "[HOST] Setting boot variables..."
if grep -q '^#*enable_uart=' "$MOUNT_DIR/boot/config.txt"; then
  sed -i 's/^#*enable_uart=.*/enable_uart=1/' "$MOUNT_DIR/boot/config.txt"
else
  echo "enable_uart=1" | tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null
fi

if grep -q '^#*hdmi_blanking=' "$MOUNT_DIR/boot/config.txt"; then
  sed -i 's/^#*hdmi_blanking=.*/hdmi_blanking=2/' "$MOUNT_DIR/boot/config.txt"
else
  echo "hdmi_blanking=2" | tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null
fi

if grep -q '^#*disable_splash=' "$MOUNT_DIR/boot/config.txt"; then
  sed -i 's/^#*disable_splash=.*/disable_splash=1/' "$MOUNT_DIR/boot/config.txt"
else
  echo "disable_splash=1" | tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null
fi

echo "[HOST] Enable i2c..."
if grep -q '^#*dtparam=i2c_arm=' "$MOUNT_DIR/boot/config.txt"; then
  sed -i 's/^#*dtparam=i2c_arm=.*/dtparam=i2c_arm=on/' "$MOUNT_DIR/boot/config.txt"
else
  echo "dtparam=i2c_arm=on" | tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null
fi
echo "i2c-dev" >> "$MOUNT_DIR/etc/modules"

echo "[Host] Enable hardware PWM..."
if grep -q '^#*dtoverlay=pwm-2chan' "$MOUNT_DIR/boot/config.txt"; then  sed -i 's/^#*dtparam=i2c_arm=.*/dtparam=i2c_arm=on/' "$MOUNT_DIR/boot/config.txt"
  sed -i 's/^#*dtoverlay=pwm-2chan.*/dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4/' "$MOUNT_DIR/boot/config.txt"
else
  echo "dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4" | tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null
fi

echo "[Host] Enable dwc2 USB driver..."
echo "dtoverlay=dwc2,dr_mode=host" | tee -a "$MOUNT_DIR/boot/config.txt" > /dev/null

if ! grep -q 'fsck.repair=yes' "$MOUNT_DIR/boot/cmdline.txt"; then
  sed -i 's/$/ fsck.repair=yes/' "$MOUNT_DIR/boot/cmdline.txt"
fi

if ! grep -q 'usbcore.autosuspend=-1' "$MOUNT_DIR/boot/cmdline.txt"; then
  sed -i 's/$/ usbcore.autosuspend=-1/' "$MOUNT_DIR/boot/cmdline.txt"
fi

if grep -qw 'quiet' "$MOUNT_DIR/boot/cmdline.txt"; then
  sed -i 's/\bquiet\b//g' "$MOUNT_DIR/boot/cmdline.txt"
fi

echo "[HOST] Cleaning up and unmounting"
rm -r "$MOUNT_DIR/var/log/journal"

sync
umount "$MOUNT_DIR/boot"
umount "$MOUNT_DIR/data"
umount "$MOUNT_DIR/dev/pts"
for d in $MOUNT_BIND_DIRS; do
  umount "$MOUNT_DIR/$d"
done
umount "$MOUNT_DIR"

echo "[HOST] Final filesystem check on all partitions"
e2fsck -fy "${LOOP_DEV}p2"
e2fsck -fy "${LOOP_DEV}p3"

losetup -d "$LOOP_DEV"

echo "[HOST] Compressing modified image"
xz -T0 -f "$IMG_WORK"

echo "[HOST] Done - flashable image: ${OUTPUT_IMG}"
