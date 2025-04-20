#!/bin/bash

# Prepare the host environment for building using chroot
# Run from root of project

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root" >&2
  exit 1
fi

BAS_IMAGE_URL="https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2023-05-03/2023-05-03-raspios-bullseye-arm64-lite.img.xz"

REQUIRED_PKGS=(parted e2fsprogs qemu-user-static binfmt-support kpartx dosfstools debootstrap xz-utils)
BASE_DIR="./build"
TMP_DIR="${BASE_DIR}/tmp"
BASE_IMAGE_PATH="${TMP_DIR}/dependencies/raspios.img.xz"

echo "[*] Checking required packages..."
for pkg in "${REQUIRED_PKGS[@]}"; do
  dpkg -s "$pkg" &>/dev/null || MISSING_PKGS+=("$pkg")
done

if [ "${#MISSING_PKGS[@]}" -gt 0 ]; then
  echo "[*] Installing missing packages: ${MISSING_PKGS[*]}"
  apt-get update
  apt-get install -y "${MISSING_PKGS[@]}"
fi

echo "[*] Creating folder structure"
mkdir -p "${TMP_DIR}"/{mnt-image,mnt-build,dependencies}
mkdir -p "${TMP_DIR}/dependencies/debs"

if [ ! -f "${BASE_IMAGE_PATH}" ]; then
  echo "[*] Fetching base image"
  wget -O "${BASE_IMAGE_PATH}" "${BAS_IMAGE_URL}"
fi
