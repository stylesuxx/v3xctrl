#!/bin/bash

# Our firstboot script is running AFTER PIs firstboot is running.

# If at all possible add functionality to the image customization script instead
# of here. Only things that really NEED to be don here, should be:
# - expands data partition to max available size
# - moves swap to data partition
# - Copy config files to data partition
# - enables overlay FS (RO mode)
# - set /boot to RO

set -xe
exec > /boot/firmware/firstboot.log 2>&1

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

echo "[v3xctrl-firstboot] Moving SWAP file to data partition..."
systemctl stop dev-zram0.swap

if [ -f /var/swap ]; then
  mv "/var/swap" "${TARGET}/swap"
fi

mkdir -p /etc/rpi/swap.conf.d
cat > /etc/rpi/swap.conf.d/99-data-partition.conf << EOF
[Main]
Mechanism=swapfile

[File]
Path=/data/swap
EOF

systemctl start dev-zram0.swap

echo "[v3xctrl-firstboot] Copy config files to persistent storage"
if [ -f "/etc/v3xctrl/config.json" ]; then
  cp "/etc/v3xctrl/config.json" "${TARGET}/config/config.json"
  chown v3xctrl:v3xctrl "${TARGET}/config/config.json"
  chmod a+r "${TARGET}/config/config.json"
fi

NM_CONNECTIONS="/etc/NetworkManager/system-connections"
if [ -d "$NM_CONNECTIONS" ] && [ -n "$(ls -A $NM_CONNECTIONS 2>/dev/null)" ]; then
  echo "[v3xctrl-firstboot] Moving NetworkManager connections to persistent storage..."

  mv "$NM_CONNECTIONS" "${TARGET}/config/NetworkManager"
  ln -s "${TARGET}/config/NetworkManager" "$NM_CONNECTIONS"
fi

echo "[v3xctrl-firstboot] Enabling overlay fs..."
v3xctrl-remount ro

echo "[v3xctrl-firstboot] Cleaning up..."
systemctl disable v3xctrl-firstboot.service
systemctl mask v3xctrl-firstboot.service
rm -f /boot/firmware/firstboot.sh

echo "[v3xctrl-firstboot] Removing firstboot warning..."
rm "/etc/profile.d/10_v3xctrl-motd-firstboot.sh"

echo "[v3xctrl-firstboot] First boot setup complete."
reboot
