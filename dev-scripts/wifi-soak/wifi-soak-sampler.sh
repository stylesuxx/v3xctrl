#!/bin/bash
# 1 Hz log of the values that could change right before an SDIO failure:
# temperature, throttle flags, ARM/core/EMMC clocks, core voltage, WiFi signal
# and rate, wlan0 transmit and receive rates in Mbit and packets per second
# with the failed-frame delta, mmc1 interrupts per second, reachability of
# the server, and the SDIO bus clock the WiFi chip runs at.
PROBE_HOST="${1:?usage: $0 PROBE_HOST}"

vc() {
  vcgencmd "$@" 2> /dev/null | cut -d= -f2 | tr -d '\n'
}

station_counter() {
  iw dev wlan0 station dump 2> /dev/null | awk -v key="$1" '$0 ~ key {print $NF; exit}'
}

read_statistic() {
  cat "/sys/class/net/wlan0/statistics/$1" 2> /dev/null || echo 0
}

mmc1_interrupts() {
  # The header lists one field per CPU, the per-CPU counts follow the irq number.
  awk 'NR == 1 {cpus = NF} /mmc1/ {total = 0; for (i = 2; i <= cpus + 1; i++) { total += $i } print total; exit}' /proc/interrupts 2> /dev/null || echo 0
}

previous_tx_bytes="$(read_statistic tx_bytes)"
previous_rx_bytes="$(read_statistic rx_bytes)"
previous_tx_packets="$(read_statistic tx_packets)"
previous_rx_packets="$(read_statistic rx_packets)"
previous_failed="$(station_counter 'tx failed:')"
previous_interrupts="$(mmc1_interrupts)"
previous_milliseconds="$(date +%s%3N)"

# A pass takes one to two seconds, so rates are scaled by the real elapsed
# time rather than assumed per second.
while true; do
  if ping -c 1 -W 1 "${PROBE_HOST}" > /dev/null 2>&1; then
    reachable=yes
  else
    reachable=no
  fi
  tx_bytes="$(read_statistic tx_bytes)"
  rx_bytes="$(read_statistic rx_bytes)"
  tx_packets="$(read_statistic tx_packets)"
  rx_packets="$(read_statistic rx_packets)"
  failed="$(station_counter 'tx failed:')"
  interrupts="$(mmc1_interrupts)"
  now_milliseconds="$(date +%s%3N)"
  elapsed_milliseconds=$(( now_milliseconds - previous_milliseconds ))
  if [ "${elapsed_milliseconds}" -lt 1 ]; then
    elapsed_milliseconds=1
  fi
  printf '%s temp=%s throttled=%s arm=%s core=%s emmc=%s volt=%s link=%s tx=%sMbit/%spps rx=%sMbit/%spps fail=%s irq=%s reach=%s mmc1=%s\n' \
    "$(date +%FT%T)" \
    "$(vc measure_temp)" \
    "$(vc get_throttled)" \
    "$(vc measure_clock arm)" \
    "$(vc measure_clock core)" \
    "$(vc measure_clock emmc)" \
    "$(vc measure_volts core)" \
    "$(iw dev wlan0 link 2> /dev/null | awk '/signal/ {s=$2} /tx bitrate/ {b=$3} END {print s "dBm/" b "Mbit"}')" \
    "$(( (tx_bytes - previous_tx_bytes) * 8 / (elapsed_milliseconds * 1000) ))" \
    "$(( (tx_packets - previous_tx_packets) * 1000 / elapsed_milliseconds ))" \
    "$(( (rx_bytes - previous_rx_bytes) * 8 / (elapsed_milliseconds * 1000) ))" \
    "$(( (rx_packets - previous_rx_packets) * 1000 / elapsed_milliseconds ))" \
    "$(( ${failed:-0} - ${previous_failed:-0} ))" \
    "$(( (${interrupts:-0} - ${previous_interrupts:-0}) * 1000 / elapsed_milliseconds ))" \
    "${reachable}" \
    "$(grep -E '^(actual clock|timing spec)' /sys/kernel/debug/mmc1/ios 2> /dev/null | sed 's/.*:[[:space:]]*//' | paste -sd/)"
  previous_milliseconds="${now_milliseconds}"
  previous_tx_bytes="${tx_bytes}"
  previous_rx_bytes="${rx_bytes}"
  previous_tx_packets="${tx_packets}"
  previous_rx_packets="${rx_packets}"
  previous_failed="${failed}"
  previous_interrupts="${interrupts}"
  sleep 1
done
