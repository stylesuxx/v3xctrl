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
  echo "[rc-firstboot] Waiting for set-wlan to finish..."
  sleep 1
done

PART="/dev/mmcblk0p3"

echo "[rc-firstboot] Resizing $PART to fill disk..."
parted -s /dev/mmcblk0 resizepart 3 100%
partprobe
sleep 2
udevadm settle
e2fsck -fy "$PART"
mount "$PART" /data && umount /data
e2fsck -fy "$PART"
resize2fs "$PART"

echo "[rc-firstboot] Updating /etc/fstab with /data and mounting"
PARTUUID=$(blkid -s PARTUUID -o value "${PART}")
tee -a "/etc/fstab" > /dev/null <<EOF
PARTUUID=${PARTUUID} /data ext4 defaults 0 2
EOF

mount /data

echo "[rc-firstboot] Linking /var/log and /var/swap"
mv "/var/log" "/data"
ln -s "/data/log" "/var/log"

dphys-swapfile swapoff
if [ -f /var/swap ]; then
  mv "/var/swap" "/data/swap"
fi
sed -i \
  -e 's|^#\?CONF_SWAPFILE=.*|CONF_SWAPFILE=/data/swap|' \
  /etc/dphys-swapfile
dphys-swapfile swapon

echo "[rc-firstboot] Move config files to persistent storage"
if [ -f "/etc/v3xctrl/config.json" ]; then
    chmod a+r "/etc/v3xctrl/config.json"
    mv "/etc/v3xctrl/config.json" "/data/config/config.json"
    ln -sf "/data/config/config.json" "/etc/v3xctrl/config.json"
fi

if [ -f "/etc/wpa_supplicant/wpa_supplicant.conf" ]; then
  mv "/etc/wpa_supplicant/wpa_supplicant.conf" "/data/config/wpa_supplicant.conf"
  ln -sf "/data/config/wpa_supplicant.conf" "/etc/wpa_supplicant/wpa_supplicant.conf"
fi

# Enable overlay fs
# This creates /boot/initrd.img* and adds boot=overlay to cmdline.txt
# In order to disable the overlay fs, it is enough to remove the boot=overlay
# parameter from cmdline.txt
#
# This needs to happen at runtime - during image generation not everything is
# in place yet.
echo "[rc-firstboot] Enabling overlay fs..."
raspi-config nonint enable_overlayfs
rc-remount ro

echo "[rc-firstboot] Cleaning up..."
systemctl disable rc-firstboot.service
systemctl mask rc-firstboot.service
rm -f /boot/firstboot.sh

echo "[rc-firstboot] First boot setup complete."
reboot
