#!/bin/bash
#
# Install the v3xctrl relay host services.
#
# Run as root from a copied source tree on the relay host. Units and the
# configuration file are installed outside the tree, so they survive the next
# copy. Re-run "base" after a copy to pick up changes to the units.
set -euo pipefail

SERVICE_USER="v3xctrl"
CONFIG_DIRECTORY="/etc/v3xctrl"
CONFIG_PATH="${CONFIG_DIRECTORY}/relay.toml"
STATE_DIRECTORY="/var/lib/v3xctrl"
UNIT_DIRECTORY="/etc/systemd/system"
TARGET="v3xctrl-relay.target"

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "${SCRIPT_DIRECTORY}/../.." && pwd)"

usage() {
  cat >&2 <<USAGE
Usage:
  install.sh base [--python PATH] [--root PATH]   install units, user, state directory, config
  install.sh add <instance>                       enable one relay instance
  install.sh remove <instance>                    disable and stop one relay instance

  --python  interpreter the services run (default: the python3 on PATH)
  --root    source tree the services run from (default: ${SOURCE_ROOT})
USAGE
  exit 2
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "install.sh must run as root" >&2
    exit 1
  fi
}

install_base() {
  local python_path="" root_path=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --python) python_path="${2:-}"; shift 2 ;;
      --root) root_path="${2:-}"; shift 2 ;;
      *) usage ;;
    esac
  done

  python_path="${python_path:-$(command -v python3)}"
  root_path="${root_path:-${SOURCE_ROOT}}"

  if [[ ! -x "${python_path}" ]]; then
    echo "Not an executable interpreter: ${python_path}" >&2
    exit 1
  fi

  if [[ ! -d "${root_path}/src/v3xctrl_relay" ]]; then
    echo "No v3xctrl source tree at ${root_path}" >&2
    exit 1
  fi

  if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
    echo "Created system user ${SERVICE_USER}"
  fi

  install -d -m 0755 -o "${SERVICE_USER}" -g "${SERVICE_USER}" "${STATE_DIRECTORY}"
  install -d -m 0755 "${CONFIG_DIRECTORY}"

  if [[ -e "${CONFIG_PATH}" ]]; then
    echo "Keeping existing ${CONFIG_PATH}"
  else
    install -m 0640 -o root -g "${SERVICE_USER}" \
      "${SCRIPT_DIRECTORY}/relay.toml.example" "${CONFIG_PATH}"
    echo "Wrote ${CONFIG_PATH}, fill in the CHANGE_ME values before starting"
  fi

  local unit
  for unit in "${SCRIPT_DIRECTORY}"/systemd/*; do
    sed -e "s|@PYTHON@|${python_path}|g" -e "s|@ROOT@|${root_path}|g" \
      "${unit}" >"${UNIT_DIRECTORY}/$(basename "${unit}")"
  done
  chmod 0644 "${UNIT_DIRECTORY}/v3xctrl-relay"*

  systemctl daemon-reload

  # The singletons belong to every deployment, so enabling them here is what
  # links them into the target. Relay instances are enabled one at a time by
  # "add", since their number is a per-host decision.
  systemctl enable "${TARGET}" v3xctrl-relay-bot.service v3xctrl-relay-stats.service >/dev/null

  echo "Installed units running ${python_path} from ${root_path}"
  echo "Next: fill in ${CONFIG_PATH}, then install.sh add <instance>"
}

add_instance() {
  local instance="${1:-}"
  [[ -n "${instance}" ]] || usage

  local unit="v3xctrl-relay-server@${instance}.service"

  if [[ ! -e "${UNIT_DIRECTORY}/v3xctrl-relay-server@.service" ]]; then
    echo "Units are not installed yet, run install.sh base first" >&2
    exit 1
  fi

  # Starting it is the real test of the configuration: a missing
  # [relay.<instance>] table, a bad port or an unreadable database all surface
  # here rather than as a unit that crash-loops unnoticed. Type=simple reports
  # success as soon as the process is forked, so is-active after a pause is
  # what actually answers the question.
  systemctl enable --now "${unit}" >/dev/null 2>&1 || true

  sleep 2

  if ! systemctl is-active --quiet "${unit}"; then
    echo "${instance} did not start, leaving it disabled:" >&2
    systemctl status --no-pager --lines=20 "${unit}" >&2 || true
    systemctl disable --now "${unit}" >/dev/null 2>&1 || true
    exit 1
  fi

  echo "Enabled and started ${unit}"
  echo "Open the port from [relay.${instance}] for UDP and TCP, and list it in stats.relay_ports"
}

remove_instance() {
  local instance="${1:-}"
  [[ -n "${instance}" ]] || usage

  local unit="v3xctrl-relay-server@${instance}.service"

  if ! systemctl disable --now "${unit}" >/dev/null 2>&1; then
    echo "Could not disable ${unit}, it may never have been enabled" >&2
    exit 1
  fi

  echo "Disabled ${unit}"
}

require_root

command="${1:-}"
shift || usage

case "${command}" in
  base) install_base "$@" ;;
  add) add_instance "$@" ;;
  remove) remove_instance "$@" ;;
  *) usage ;;
esac
