#!/bin/bash
# Pushes the soak test to a Pi, controls it, and pulls results. Nothing lands
# in the image build; "remove" takes it all off the Pi again.
set -eu

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_STAGE="/tmp/wifi-soak"

usage() {
  cat << USAGE
Usage: $0 <command> <user@pi-host>

Commands:
  install   Copy the soak files to the Pi, enable the service, reboot into the first cycle
  status    Print the cycle counts and one line per hit
  details   Same as status, plus events, snapshots and sampler lines per hit
  stop      End the running cycle without rebooting and pause the loop
  resume    Clear the pause and start a cycle now
  fetch     Copy /var/log/wifi-soak into ./results/<host>-<timestamp>/
  bundle    fetch plus the status and details output, packed into one .tar.gz to attach to an issue
  remove    Disable and delete everything the installer put on the Pi, keep the logs
  purge     Same as remove, and delete the logs too

Before install: edit wifi-soak.conf, then run "iperf3 -s -p 5201" and
"iperf3 -s -p 5202" on the host it names.
USAGE
}

COMMAND="${1:-}"
TARGET="${2:-}"
if [ -z "${COMMAND}" ] || [ -z "${TARGET}" ]; then
  usage
  exit 1
fi

remote() {
  # shellcheck disable=SC2029 # arguments are meant to expand on this side
  ssh "${TARGET}" sudo "$@"
}

case "${COMMAND}" in
  install)
    # shellcheck disable=SC2029 # REMOTE_STAGE is a fixed path, expanded here on purpose
    ssh "${TARGET}" "rm -rf ${REMOTE_STAGE} && mkdir -p ${REMOTE_STAGE}"
    scp -q \
      "${SCRIPT_DIRECTORY}/wifi-soak.sh" \
      "${SCRIPT_DIRECTORY}/wifi-soak-sampler.sh" \
      "${SCRIPT_DIRECTORY}/wifi-soak-report.sh" \
      "${SCRIPT_DIRECTORY}/wifi-soak.conf" \
      "${SCRIPT_DIRECTORY}/wifi-soak.service" \
      "${SCRIPT_DIRECTORY}/pi-install.sh" \
      "${SCRIPT_DIRECTORY}/pi-remove.sh" \
      "${TARGET}:${REMOTE_STAGE}/"
    remote bash "${REMOTE_STAGE}/pi-install.sh"
    echo "rebooting ${TARGET} into the first cycle"
    remote systemctl reboot || true
    ;;
  status)
    remote /opt/wifi-soak/wifi-soak-report.sh
    ;;
  details)
    remote /opt/wifi-soak/wifi-soak-report.sh --details
    ;;
  stop)
    remote touch /var/log/wifi-soak/stop
    remote systemctl stop wifi-soak.service
    echo "paused, the Pi stays up for inspection"
    ;;
  resume)
    remote rm -f /var/log/wifi-soak/stop
    remote systemctl start wifi-soak.service
    echo "cycle started"
    ;;
  fetch)
    destination="${SCRIPT_DIRECTORY}/results/${TARGET#*@}-$(date +%Y%m%dT%H%M%S)"
    mkdir -p "${destination}"
    ssh "${TARGET}" sudo tar -C /var/log -cf - wifi-soak | tar -C "${destination}" -xf -
    echo "results in ${destination}"
    ;;
  bundle)
    name="${TARGET#*@}-$(date +%Y%m%dT%H%M%S)"
    destination="${SCRIPT_DIRECTORY}/results/${name}"
    mkdir -p "${destination}"
    remote /opt/wifi-soak/wifi-soak-report.sh > "${destination}/status.txt"
    remote /opt/wifi-soak/wifi-soak-report.sh --details > "${destination}/details.txt"
    ssh "${TARGET}" 'uname -a; cat /proc/device-tree/model; echo; vcgencmd version; vcgencmd measure_volts core; grep -E "^(over_voltage|arm_freq|core_freq|force_turbo)" /boot/firmware/config.txt; sudo dmesg | grep -m1 "brcmf_c_preinit_dcmds: Firmware"' > "${destination}/system.txt" 2>&1
    cp "${SCRIPT_DIRECTORY}/wifi-soak.conf" "${destination}/wifi-soak.conf"
    ssh "${TARGET}" sudo tar -C /var/log -cf - wifi-soak | tar -C "${destination}" -xf -
    ssh "${TARGET}" 'sudo journalctl -k -b all -o short-iso --no-pager' > "${destination}/kernel-journal-all-boots.txt" 2>&1
    tar -C "${SCRIPT_DIRECTORY}/results" -czf "${destination}.tar.gz" "${name}"
    cat "${destination}/status.txt"
    echo
    echo "bundle: ${destination}.tar.gz"
    ;;
  remove)
    remote /opt/wifi-soak/pi-remove.sh
    ;;
  purge)
    remote /opt/wifi-soak/pi-remove.sh --purge
    ;;
  *)
    usage
    exit 1
    ;;
esac
