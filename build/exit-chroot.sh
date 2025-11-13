#!/bin/bash
set -e

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root" >&2
  exit 1
fi

TMP_DIR="./build/tmp"
MOUNT_DIR="${TMP_DIR}/mnt-build"
MOUNT_BIND_DIRS="dev proc sys"
LOOP_STATE_FILE="${TMP_DIR}/.loop_device"

if [ ! -f "$LOOP_STATE_FILE" ]; then
  echo "No active chroot session found" >&2
  exit 1
fi

LOOP_DEV=$(cat "$LOOP_STATE_FILE")

echo "[HOST] Cleaning up and unmounting"
umount -lf "$MOUNT_DIR/boot" 2>/dev/null || true
umount -lf "$MOUNT_DIR/dev/pts" 2>/dev/null || true
for d in $MOUNT_BIND_DIRS; do
  umount -lf "$MOUNT_DIR/$d" 2>/dev/null || true
done
umount -lf "$MOUNT_DIR" 2>/dev/null || true
losetup -d "$LOOP_DEV" 2>/dev/null || true

rm -f "$LOOP_STATE_FILE"
echo "[HOST] Cleanup complete"
