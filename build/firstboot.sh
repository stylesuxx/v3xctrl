#!/bin/bash

# This firstboot script is running AFTER cloud-init is finished.

# If at all possible add functionality to the image customization script instead
# of here. Only things that really NEED to be don here, should be:
# - expands data partition to max available size
# - Copy configs - created during cloud-init - to data partition
# - enables overlay FS (RO mode)
# - Disables serial console on success
# - Disables firstboot warning MOTD
# - Cleanup

set -xe
exec > /boot/firmware/firstboot.log 2>&1

PART="/dev/mmcblk0p3"
TARGET="/data"

# Just in case data was already added to fstab in a previous run but failed
# somewhere else inbetween.
echo "[v3xctrl-firstboot] Ensuring $PART is unmounted..."
if grep -qs "$TARGET" /proc/mounts; then
  umount "$TARGET"
fi

echo "[v3xctrl-firstboot] Resizing $PART to fill disk..."
parted -s /dev/mmcblk0 resizepart 3 100%

echo "[v3xctrl-firstboot] Probing partitions..."
partprobe /dev/mmcblk0
sleep 5
udevadm settle

echo "[v3xctrl-firstboot] Forcing filesystem check on $PART..."
e2fsck -fy "$PART"

echo "[v3xctrl-firstboot] Resizing filesystem on $PART..."
resize2fs "$PART"

echo "[v3xctrl-firstboot] Final filesystem check on $PART..."
e2fsck -fy "$PART"

if ! grep -q "${TARGET}[[:space:]]" /etc/fstab; then
  echo "[v3xctrl-firstboot] Updating /etc/fstab with /data and mounting..."
  PARTUUID=$(blkid -s PARTUUID -o value "${PART}")
  tee -a "/etc/fstab" > /dev/null <<EOF
PARTUUID=${PARTUUID} ${TARGET} ext4 defaults 0 2
EOF
fi

echo "[v3xctrl-firstboot] Mounting ${TARGET} and copying config files..."
mount "$TARGET"

NM_CONNECTIONS="/etc/NetworkManager/system-connections"
if [ -d "$NM_CONNECTIONS" ] && [ -n "$(ls -A $NM_CONNECTIONS 2>/dev/null)" ]; then
  echo "[v3xctrl-firstboot] Moving NetworkManager connections to persistent storage..."

  mv "$NM_CONNECTIONS" "${TARGET}/config/NetworkManager"
  ln -s "${TARGET}/config/NetworkManager" "$NM_CONNECTIONS"
fi

NETPLAN="/etc/netplan"
if [ -d "$NETPLAN" ] && [ -n "$(ls -A $NETPLAN 2>/dev/null)" ]; then
  echo "[v3xctrl-firstboot] Moving netplan to persistent storage..."

  mv "$NETPLAN" "${TARGET}/config/netplan"
  ln -s "${TARGET}/config/netplan" "$NETPLAN"
fi

echo "[v3xctrl-firstboot] Enabling overlay fs..."
v3xctrl-remount ro

#echo "[v3xctrl-firstboot] Disabling serial console..."
#sed -i 's/console=serial0,115200 //g' /boot/firmware/cmdline.txt

echo "[v3xctrl-firstboot] Cleaning up..."
systemctl disable v3xctrl-firstboot.service
rm -f /boot/firmware/firstboot.sh

echo "[v3xctrl-firstboot] Removing firstboot warning..."
rm -f "/etc/profile.d/10_v3xctrl-motd-firstboot.sh"

echo "[v3xctrl-firstboot] First boot setup complete, rebooting..."
sync
reboot
