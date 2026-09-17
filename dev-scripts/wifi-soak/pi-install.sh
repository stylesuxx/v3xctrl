#!/bin/bash
# Installs the soak loop on this Pi. Run as root from the directory holding
# the soak files. Everything it touches is undone by pi-remove.sh.
set -eu

SOURCE_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIRECTORY="/opt/wifi-soak"
LOG_DIRECTORY="/var/log/wifi-soak"
WATCHDOG_DROPIN="/etc/systemd/system.conf.d/wifi-soak-watchdog.conf"
JOURNALD_DROPIN="/etc/systemd/journald.conf.d/zz-wifi-soak.conf"
SSHD_DROPIN="/etc/ssh/sshd_config.d/wifi-soak.conf"

for tool in iperf3 vcgencmd; do
  if ! command -v "${tool}" > /dev/null; then
    echo "missing on the Pi: ${tool}" >&2
    exit 1
  fi
done

mkdir -p "${INSTALL_DIRECTORY}" "${LOG_DIRECTORY}"
install -m 755 \
  "${SOURCE_DIRECTORY}/wifi-soak.sh" \
  "${SOURCE_DIRECTORY}/wifi-soak-sampler.sh" \
  "${SOURCE_DIRECTORY}/wifi-soak-report.sh" \
  "${SOURCE_DIRECTORY}/pi-remove.sh" \
  "${INSTALL_DIRECTORY}/"
install -m 644 "${SOURCE_DIRECTORY}/wifi-soak.conf" "${INSTALL_DIRECTORY}/"
install -m 644 "${SOURCE_DIRECTORY}/wifi-soak.service" /etc/systemd/system/

# Persistent journal so the kernel log of every boot survives the reboot.
# The image runs journald with Storage=volatile, the drop-in overrides it.
if [ ! -d /var/log/journal ]; then
  mkdir -p /var/log/journal
  touch "${LOG_DIRECTORY}/.journal-directory-created"
fi
mkdir -p "$(dirname "${JOURNALD_DROPIN}")"
printf '[Journal]\nStorage=persistent\n' > "${JOURNALD_DROPIN}"

# The UDP flood fills the WiFi best-effort queue, which left ssh replies from
# the Pi crawling. Marking sshd traffic as voice class puts it in the
# highest-priority WMM queue ahead of the flood.
mkdir -p "$(dirname "${SSHD_DROPIN}")"
printf 'IPQoS cs6 cs6\n' > "${SSHD_DROPIN}"

# Hardware watchdog turns a hard kernel hang into a reboot instead of a
# stalled loop. Applied by the reboot that starts the first cycle.
mkdir -p "$(dirname "${WATCHDOG_DROPIN}")"
printf '[Manager]\nRuntimeWatchdogSec=30\n' > "${WATCHDOG_DROPIN}"

rm -f "${LOG_DIRECTORY}/stop"
systemctl daemon-reload
systemctl enable wifi-soak.service
echo "installed"
