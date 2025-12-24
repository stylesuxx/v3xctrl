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

set -e
exec > >(tee /boot/firmware/firstboot.log) 2>&1

# Record script start time in milliseconds
START_TIME=$(date +%s%3N)

# Helper function to echo with relative timestamp (MM:SS.mmm)
log() {
  local current_time=$(date +%s%3N)
  local elapsed=$((current_time - START_TIME))
  local minutes=$((elapsed / 60000))
  local seconds=$(((elapsed % 60000) / 1000))
  local millis=$((elapsed % 1000))
  printf "[%02d:%02d.%03d] %s\n" "$minutes" "$seconds" "$millis" "$*"
}

PART="/dev/mmcblk0p3"
TARGET="/data"

# Just in case data was already added to fstab in a previous run but failed
# somewhere else inbetween.
log "Ensuring $PART is unmounted..."
if grep -qs "$TARGET" /proc/mounts; then
  umount "$TARGET"
fi

log "Resizing $PART to fill disk..."
parted -s /dev/mmcblk0 resizepart 3 100%

log "Probing partitions..."
partprobe /dev/mmcblk0
sleep 5
udevadm settle

log "Forcing filesystem check on $PART..."
e2fsck -fy "$PART"

log "Resizing filesystem on $PART..."
resize2fs "$PART"

log "Final filesystem check on $PART..."
e2fsck -fy "$PART"

if ! grep -q "${TARGET}[[:space:]]" /etc/fstab; then
  log "Updating /etc/fstab with /data and mounting..."
  PARTUUID=$(blkid -s PARTUUID -o value "${PART}")
  tee -a "/etc/fstab" > /dev/null <<EOF
PARTUUID=${PARTUUID} ${TARGET} ext4 defaults 0 2
EOF
fi

log "Mounting ${TARGET} and copying config files..."
mount "$TARGET"

NM_CONNECTIONS="/etc/NetworkManager/system-connections"
if [ -d "$NM_CONNECTIONS" ] && [ -n "$(ls -A $NM_CONNECTIONS 2>/dev/null)" ]; then
  log "Moving NetworkManager connections to persistent storage..."

  mv "$NM_CONNECTIONS" "${TARGET}/config/NetworkManager"
  ln -s "${TARGET}/config/NetworkManager" "$NM_CONNECTIONS"
fi

NETPLAN="/etc/netplan"
if [ -d "$NETPLAN" ] && [ -n "$(ls -A $NETPLAN 2>/dev/null)" ]; then
  log "Moving netplan to persistent storage..."

  mv "$NETPLAN" "${TARGET}/config/netplan"
  ln -s "${TARGET}/config/netplan" "$NETPLAN"
fi

log "Enabling overlay fs..."
v3xctrl-remount ro

#log "Disabling serial console..."
#sed -i 's/console=serial0,115200 //g' /boot/firmware/cmdline.txt

log "Cleaning up..."
systemctl disable v3xctrl-firstboot.service
rm -f /boot/firmware/firstboot.sh
rm -f "/etc/profile.d/10_v3xctrl-motd-firstboot.sh"

log "Syncing..."
sync

log "Rebooting..."
reboot
