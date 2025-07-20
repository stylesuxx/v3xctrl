#!/bin/bash

# Our firstboot script is running AFTER PIs firstboot is running.
# Unfortunately the set-wlan service is configured during this first boot, but
# only actually executed on the second boot - where we want to run our custom
# script. But we need to wait until the set-wlan service has finished executing
# before we can set the partitions RO - otherwise we risk that the set-wlan
# service does it's job, but never actually deletes itself.

# If at all possible add functionality to the image customization script instead
# of here. Only things that really NEED to be don here, should be.

set -xe
exec > /boot/firstboot.log 2>&1

while [ -f "/var/lib/raspberrypi-sys-mods/set-wlan" ]; do
  echo "[v3xctrl-firstboot] Waiting for set-wlan to finish..."
  sleep 1
done

PART="/dev/mmcblk0p3"
TARGET="/data"

echo "[v3xctrl-firstboot] Resizing $PART to fill disk..."
parted -s /dev/mmcblk0 resizepart 3 100%

echo "[v3xctrl-firstboot] Probing partitions..."
partprobe
sleep 2
udevadm settle

echo "[v3xctrl-firstboot] Cleaning $PART..."
e2fsck -fy "$PART"

echo "[v3xctrl-firstboot] Test mounting/unmounting $PART..."
mount "$PART" "$TARGET"
umount "$TARGET"

echo "[v3xctrl-firstboot] Cleaning $PART..."
e2fsck -fy "$PART"

echo "[v3xctrl-firstboot] Resizing $PART..."
resize2fs "$PART"

if ! grep -q "${TARGET}[[:space:]]" /etc/fstab; then
  echo "[v3xctrl-firstboot] Updating /etc/fstab with /data and mounting..."
  PARTUUID=$(blkid -s PARTUUID -o value "${PART}")
  tee -a "/etc/fstab" > /dev/null <<EOF
PARTUUID=${PARTUUID} ${TARGET} ext4 defaults 0 2
EOF
fi

echo "[v3xctrl-firstboot] Mounting ${TARGET} and creating folder structure..."
mount "$TARGET"
mkdir -p "${TARGET}/config"

dphys-swapfile swapoff
if [ -f /var/swap ]; then
  mv "/var/swap" "${TARGET}/swap"
fi
sed -i \
  -e 's|^#\?CONF_SWAPFILE=.*|CONF_SWAPFILE=/data/swap|' \
  /etc/dphys-swapfile
dphys-swapfile swapon

echo "[v3xctrl-firstboot] Copy config files to persistent storage"
if [ -f "/etc/v3xctrl/config.json" ]; then
  cp "/etc/v3xctrl/config.json" "${TARGET}/config/config.json"
  chown v3xctrl:v3xctrl "${TARGET}/config/config.json"
  chmod a+r "${TARGET}/config/config.json"
fi

if [ -f "/etc/wpa_supplicant/wpa_supplicant.conf" ]; then
  mv "/etc/wpa_supplicant/wpa_supplicant.conf" "${TARGET}/config/wpa_supplicant.conf"
  ln -sf "${TARGET}/config/wpa_supplicant.conf" "/etc/wpa_supplicant/wpa_supplicant.conf"
fi

# Enable overlay fs
# This creates /boot/initrd.img* and adds boot=overlay to cmdline.txt
# In order to disable the overlay fs, it is enough to remove the boot=overlay
# parameter from cmdline.txt
#
# This needs to happen at runtime - during image generation not everything is
# in place yet.
echo "[v3xctrl-firstboot] Enabling overlay fs..."
raspi-config nonint enable_overlayfs

echo "[v3xctrl-firstboot] Switching to read-only mode..."
v3xctrl-remount ro

echo "[v3xctrl-firstboot] Setting /boot to RO via /etc/fstab"
sed -i '/\/boot/ s|\(/boot[[:space:]]\+vfat[[:space:]]\+\)[^[:space:]]\+|\1ro|' /etc/fstab

echo "[v3xctrl-firstboot] Cleaning up..."
systemctl disable v3xctrl-firstboot.service
systemctl mask v3xctrl-firstboot.service
rm -f /boot/firstboot.sh

echo "[v3xctrl-firstboot] Updating MOTD..."
cp "$MOUNT_DIR/etc/profile.d/v3xctrl-motd-clean.sh" "$MOUNT_DIR/etc/profile.d/v3xctrl-motd.sh"

echo "[v3xctrl-firstboot] First boot setup complete."
reboot
