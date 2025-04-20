#!/bin/bash

# Our firstboot script is running AFTER PIs firstboot is running.
# Unfortunately the set-wlan service is configured during this first boot, but
# only actually executed on the second boot - where we want to run our custom
# script. But we need to wait until the set-wlan service has finished executing
# before we can set the partitions RO - otherwise we risk that the set-wlan
# service does it's job, but never actually deletes itself.

set -xe
exec > /boot/firstboot.log 2>&1

#local cmdline="/boot/cmdline.txt"

while [ -f "/var/lib/raspberrypi-sys-mods/set-wlan" ]; do
  echo "[rc-firstboot] Waiting for set-wlan to finish..."
  sleep 1
done

PART="/dev/mmcblk0p3"

# Preferably we do this during image creation, but those configs are not yet in
# place and are only generated during firstboot.
echo "[rc-firstboot] Moving configs into place..."
if [ -f "/etc/wpa_supplicant/wpa_supplicant.conf" ]; then
  mv "/etc/wpa_supplicant/wpa_supplicant.conf" "/data/config/wpa_supplicant.conf"
  ln -sf /data/config/wpa_supplicant.conf "/etc/wpa_supplicant/wpa_supplicant.conf"
fi

echo "[rc-firstboot] Resizing $PART to fill disk..."
umount "${PART}"
parted -s /dev/mmcblk0 resizepart 3 100%
partprobe
e2fsck -fy "$PART"
resize2fs "$PART"

# Set to read-only mode.
# initrd.img has already been built during image generation
rc-remount ro

echo "[rc-firstboot] Cleaning up..."
systemctl disable rc-firstboot.service
systemctl mask rc-firstboot.service
rm -f /boot/firstboot.sh

echo "[rc-firstboot] First boot setup complete."
reboot
