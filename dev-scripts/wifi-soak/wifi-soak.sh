#!/bin/bash
# One soak cycle per boot: wait for WiFi, put load on it, watch the kernel log
# for the brcmfmac/SDIO failure signature, record the outcome, reboot.
# Started by wifi-soak.service, runs as root.
set -u

INSTALL_DIRECTORY="/opt/wifi-soak"
LOG_DIRECTORY="/var/log/wifi-soak"
STOP_FILE="${LOG_DIRECTORY}/stop"
SUMMARY_FILE="${LOG_DIRECTORY}/summary"
CYCLE_DIRECTORY="${LOG_DIRECTORY}/cycles"
SIGNATURE='Controller never released inhibit|RXHEADER FAILED|failed backplane access|brcmf_sdio_htclk|Timeout waiting for hardware interrupt|bcm2835_mmc_transfer_dma|brcmf_sdio_txfail|HW header checksum error|dongle is not responding|firmware trap'
# Lines worth keeping next to the signatures without ending the cycle.
WARNING_SIGNATURE='MMC controller hung|resumed on timeout|bcdc_msg failed|Failed to get bss info|brcmf_sdio_rxfail|brcmf_sdio_hdparse|CMD53'

# shellcheck source=wifi-soak.conf
source "${INSTALL_DIRECTORY}/wifi-soak.conf"

mkdir -p "${CYCLE_DIRECTORY}"
CYCLE_ID="$(date +%Y%m%dT%H%M%S)"
OUTPUT_PREFIX="${CYCLE_DIRECTORY}/${CYCLE_ID}"
BACKGROUND_PIDS=()

uptime_seconds() {
  cut -d. -f1 /proc/uptime
}

record_result() {
  local result="$1"
  local detail="${2:-}"
  echo "${CYCLE_ID} boot=$(cut -c1-8 /proc/sys/kernel/random/boot_id) uptime=$(uptime_seconds)s temp=$(vcgencmd measure_temp | cut -d= -f2) result=${result} ${detail}" >> "${SUMMARY_FILE}"
}

stop_background_jobs() {
  for pid in "${BACKGROUND_PIDS[@]}"; do
    kill "${pid}" 2> /dev/null
  done
  pkill -f "iperf3 -c" 2> /dev/null
  pkill -f "journalctl -k -f" 2> /dev/null
  pkill rpicam-vid 2> /dev/null
  pkill stress-ng 2> /dev/null
}

end_cycle() {
  dmesg -T > "${OUTPUT_PREFIX}.dmesg"
  # Let the sampler capture the seconds after the event.
  sleep 5
  stop_background_jobs
  # The reboot stops this unit, and the TERM trap must not add a second
  # result line for the same cycle.
  trap - TERM INT
  systemctl reboot
  exit 0
}

finish_cycle() {
  local result="$1"
  local detail="${2:-}"
  record_result "${result}" "${detail}"
  end_cycle
}

# Snapshot of the WiFi and SDIO state, taken at the first signature and at
# the end of a cycle that had one.
capture_state() {
  local label="$1"
  {
    echo "== $(date +%FT%T) uptime=$(uptime_seconds)s label=${label}"
    echo "== throttled"
    vcgencmd get_throttled
    echo "== mmc1 ios"
    cat /sys/kernel/debug/mmc1/ios
    echo "== interrupts"
    grep -E 'CPU0|mmc|sdio' /proc/interrupts
    echo "== wlan0 link"
    iw dev wlan0 link
    echo "== station dump"
    iw dev wlan0 station dump
    echo "== wlan0 statistics"
    ip -s -s link show wlan0
    echo "== brcmfmac debugfs"
    for entry in /sys/kernel/debug/brcmfmac/*/* /sys/kernel/debug/ieee80211/phy0/brcmfmac/*; do
      if [ -f "${entry}" ]; then
        echo "-- ${entry}"
        head -n 200 "${entry}"
      fi
    done
    echo "== dmesg tail"
    dmesg -T | tail -n 60
  } > "${OUTPUT_PREFIX}.state-${label}" 2>&1
}

# "systemctl stop" ends the cycle without a reboot so the Pi can be inspected.
trap 'stop_background_jobs; record_result stopped; exit 0' TERM INT

if [ -e "${STOP_FILE}" ]; then
  echo "stop file present, not starting a cycle" >&2
  exit 0
fi

# A "started" line with no matching result line afterwards marks a boot that
# hung or was reset by the watchdog before the cycle could finish.
record_result started

wait_for_network() {
  local deadline=$(( $(uptime_seconds) + NETWORK_TIMEOUT_SECONDS ))
  while [ "$(uptime_seconds)" -lt "${deadline}" ]; do
    if ip -4 addr show wlan0 2> /dev/null | grep -q inet && ping -c 1 -W 2 "${IPERF_SERVER}" > /dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

if ! wait_for_network; then
  finish_cycle no-network "wlan0 had no route to ${IPERF_SERVER} within ${NETWORK_TIMEOUT_SECONDS}s"
fi

# WiFi firmware console into the kernel log. Effective when the driver is built
# with CONFIG_BRCMDBG, harmless otherwise.
if [ -w /sys/module/brcmfmac/parameters/debug ]; then
  echo 0x100000 > /sys/module/brcmfmac/parameters/debug
fi

"${INSTALL_DIRECTORY}/wifi-soak-sampler.sh" "${IPERF_SERVER}" > "${OUTPUT_PREFIX}.sampler" &
BACKGROUND_PIDS+=($!)

if [ "${HEAT_LOAD_CPUS}" -gt 0 ] && command -v stress-ng > /dev/null; then
  stress-ng --cpu "${HEAT_LOAD_CPUS}" --quiet &
  BACKGROUND_PIDS+=($!)
fi

if [ "${CAMERA_STREAM}" -eq 1 ] && command -v rpicam-vid > /dev/null; then
  rpicam-vid -t 0 --nopreview --width 1280 --height 720 --framerate 30 --bitrate 1800000 \
    --inline -o "udp://${IPERF_SERVER}:${CAMERA_PORT}" > "${OUTPUT_PREFIX}.camera" 2>&1 &
  BACKGROUND_PIDS+=($!)
fi

# iperf3 reconnects if the server drops out, so a server-side hiccup does not
# end the load early. forceflush writes every interval line immediately so the
# file shows the rate at the moment of a failure.
run_iperf_client() {
  local port="$1"
  local arguments="$2"
  local logfile="$3"
  while true; do
    # shellcheck disable=SC2086 # arguments is a list of flags by design
    iperf3 -c "${IPERF_SERVER}" -p "${port}" ${arguments} -t "${CYCLE_SECONDS}" --forceflush >> "${logfile}" 2>&1
    sleep 10
  done
}

run_iperf_client "${IPERF_PORT}" "${IPERF_ARGUMENTS}" "${OUTPUT_PREFIX}.iperf" &
BACKGROUND_PIDS+=($!)
if [ -n "${IPERF_REVERSE_ARGUMENTS}" ]; then
  run_iperf_client "${IPERF_REVERSE_PORT}" "${IPERF_REVERSE_ARGUMENTS} -R" "${OUTPUT_PREFIX}.iperf-rx" &
  BACKGROUND_PIDS+=($!)
fi

# Every failure signature goes to .trigger, signatures and warnings both go
# to .events, each line as soon as the kernel logs it.
(
  journalctl -k -f -n 0 -o short-iso \
    | grep --line-buffered -E "${SIGNATURE}|${WARNING_SIGNATURE}" \
    | while read -r line; do
        echo "${line}" >> "${OUTPUT_PREFIX}.events"
        if echo "${line}" | grep -q -E "${SIGNATURE}"; then
          echo "${line}" >> "${OUTPUT_PREFIX}.trigger"
        fi
      done
) &
BACKGROUND_PIDS+=($!)

deadline=$(( $(uptime_seconds) + CYCLE_SECONDS ))
first_hit_recorded=0
while [ "$(uptime_seconds)" -lt "${deadline}" ]; do
  if [ "${first_hit_recorded}" -eq 0 ] && [ -s "${OUTPUT_PREFIX}.trigger" ]; then
    first_hit_recorded=1
    record_result hit "$(head -n 1 "${OUTPUT_PREFIX}.trigger")"
    capture_state hit
    if [ "${REBOOT_ON_HIT}" -eq 1 ]; then
      end_cycle
    fi
  fi
  sleep 1
done

if [ -s "${OUTPUT_PREFIX}.trigger" ]; then
  if ping -c 2 -W 2 "${IPERF_SERVER}" > /dev/null 2>&1; then
    link=alive
  else
    link=dead
  fi
  capture_state end
  finish_cycle hit-end "signatures=$(wc -l < "${OUTPUT_PREFIX}.trigger") events=$(wc -l < "${OUTPUT_PREFIX}.events") link=${link}"
fi
finish_cycle clean
