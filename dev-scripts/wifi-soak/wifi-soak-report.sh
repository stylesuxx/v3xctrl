#!/bin/bash
# Summarizes every soak cycle recorded on this Pi. Run as root. Prints the
# counts and one line per hit, "--details" adds the events, snapshots and
# sampler lines around each hit.
LOG_DIRECTORY="/var/log/wifi-soak"
SUMMARY_FILE="${LOG_DIRECTORY}/summary"
CYCLE_DIRECTORY="${LOG_DIRECTORY}/cycles"
SHOW_DETAILS=0
if [ "${1:-}" = "--details" ]; then
  SHOW_DETAILS=1
fi

if [ ! -s "${SUMMARY_FILE}" ]; then
  echo "no cycles recorded yet"
  exit 0
fi

# Cycles recorded before a file type existed print "?" for it.
count_lines() {
  if [ -f "$1" ]; then
    wc -l < "$1"
  else
    echo '?'
  fi
}

# Counts are per cycle id, so a cycle is counted once whatever it logged.
count_result() {
  grep "result=$1" "${SUMMARY_FILE}" | cut -d' ' -f1 | sort -u | wc -l
}

# The cycle of the current boot is still running and is never counted here.
current_boot="$(cut -c1-8 /proc/sys/kernel/random/boot_id)"
unfinished=0
while read -r cycle_id; do
  if grep "^${cycle_id} " "${SUMMARY_FILE}" | grep -q "boot=${current_boot}"; then
    continue
  fi
  if ! grep "^${cycle_id} " "${SUMMARY_FILE}" | grep -q -v 'result=started'; then
    unfinished=$(( unfinished + 1 ))
  fi
done < <(cut -d' ' -f1 "${SUMMARY_FILE}" | sort -u)
journal_boots="$(journalctl --list-boots --quiet 2> /dev/null | wc -l)"
journal_signatures="$(journalctl -k -b all -o short-iso --no-pager 2> /dev/null | grep -c -E 'Controller never released inhibit|RXHEADER FAILED|failed backplane access')"

echo "cycles=$(cut -d' ' -f1 "${SUMMARY_FILE}" | sort -u | wc -l) hit=$(count_result 'hit ') clean=$(count_result clean) no-network=$(count_result no-network) stopped=$(count_result stopped)"
echo "started but never finished, hard hangs or watchdog resets: ${unfinished}"
echo "boots in the persistent journal: ${journal_boots}, signature lines across them: ${journal_signatures}"
if [ -e "${LOG_DIRECTORY}/stop" ]; then
  echo "stop file present, loop is paused"
fi
if grep -q 'result=hit ' "${SUMMARY_FILE}"; then
  echo
  printf '%-16s %8s %8s %11s %7s %s\n' cycle hit_at temp signatures events link_at_end
fi

grep 'result=hit ' "${SUMMARY_FILE}" | while read -r line; do
  cycle_id="${line%% *}"
  hit_uptime="$(echo "${line}" | grep -o 'uptime=[0-9]*s' | cut -d= -f2)"
  hit_temp="$(echo "${line}" | grep -o "temp=[^ ]*" | cut -d= -f2)"
  end_line="$(grep "^${cycle_id} " "${SUMMARY_FILE}" | grep 'result=hit-end')"
  if [ -n "${end_line}" ]; then
    signatures="$(echo "${end_line}" | grep -o 'signatures=[0-9]*' | cut -d= -f2)"
    events="$(echo "${end_line}" | grep -o 'events=[0-9]*' | cut -d= -f2)"
    link="$(echo "${end_line}" | grep -o 'link=[a-z]*' | cut -d= -f2)"
  else
    signatures="$(count_lines "${CYCLE_DIRECTORY}/${cycle_id}.trigger")"
    events="$(count_lines "${CYCLE_DIRECTORY}/${cycle_id}.events")"
    link="rebooted"
  fi
  printf '%-16s %8s %8s %11s %7s %s\n' "${cycle_id}" "${hit_uptime}" "${hit_temp}" "${signatures}" "${events}" "${link}"
done

if [ "${SHOW_DETAILS}" -eq 0 ]; then
  exit 0
fi

grep -E 'result=(hit |no-network)' "${SUMMARY_FILE}" | while read -r line; do
  cycle_id="${line%% *}"
  echo
  echo "== ${line}"
  grep "^${cycle_id} " "${SUMMARY_FILE}" | grep 'result=hit-end' | sed 's/^/== /'
  echo "-- signatures and warnings during the cycle"
  cut -c1-140 "${CYCLE_DIRECTORY}/${cycle_id}.events" 2> /dev/null | head -n 40
  echo "-- state snapshots"
  ls "${CYCLE_DIRECTORY}/${cycle_id}".state-* 2> /dev/null
  echo "-- last 15 sampler lines up to the event"
  tail -n 15 "${CYCLE_DIRECTORY}/${cycle_id}.sampler" 2> /dev/null
  echo "-- kernel log, brcmfmac and mmc1 lines around the event"
  grep -E 'brcmfmac|mmc1|phy0' "${CYCLE_DIRECTORY}/${cycle_id}.dmesg" 2> /dev/null | grep -v CONSOLE | tail -n 25
done
