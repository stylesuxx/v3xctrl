#!/bin/bash
# Removes the soak loop from this Pi. Run as root. Logs under /var/log/wifi-soak
# stay unless --purge is given.
set -eu

INSTALL_DIRECTORY="/opt/wifi-soak"
LOG_DIRECTORY="/var/log/wifi-soak"
WATCHDOG_DROPIN="/etc/systemd/system.conf.d/wifi-soak-watchdog.conf"
JOURNALD_DROPIN="/etc/systemd/journald.conf.d/zz-wifi-soak.conf"
SSHD_DROPIN="/etc/ssh/sshd_config.d/wifi-soak.conf"

mkdir -p "${LOG_DIRECTORY}"
touch "${LOG_DIRECTORY}/stop"
systemctl disable --now wifi-soak.service 2> /dev/null || true
rm -f /etc/systemd/system/wifi-soak.service "${WATCHDOG_DROPIN}" "${JOURNALD_DROPIN}" "${SSHD_DROPIN}"

if [ -e "${LOG_DIRECTORY}/.journal-directory-created" ]; then
  rm -rf /var/log/journal
fi
systemctl restart systemd-journald
systemctl reload ssh 2> /dev/null || systemctl reload sshd 2> /dev/null || true

rm -rf "${INSTALL_DIRECTORY}"
systemctl daemon-reload
systemctl daemon-reexec

if [ "${1:-}" = "--purge" ]; then
  rm -rf "${LOG_DIRECTORY}"
fi
echo "removed"
