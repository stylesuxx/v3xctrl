#!/bin/bash
#
# Install the v3xctrl relay host services.
#
# Run as root from a copied source tree on the relay host. Units and the
# configuration file are installed outside the tree, so they survive the next
# copy. Re-run "base" after a copy to pick up changes to the units.
#
# A deployment name installs a second, independent set of units from another
# source tree, so a dev tree can be deployed and restarted without touching
# production. Both read /etc/v3xctrl/relay.toml and share the state directory,
# so an instance of either deployment just needs its own [relay.<instance>]
# table and port.
set -euo pipefail

SERVICE_USER="v3xctrl"
CONFIG_DIRECTORY="/etc/v3xctrl"
CONFIG_PATH="${CONFIG_DIRECTORY}/relay.toml"
STATE_DIRECTORY="/var/lib/v3xctrl"
UNIT_DIRECTORY="/etc/systemd/system"

# Empty means the production deployment, which owns the unprefixed unit names.
deployment_name=""

# One Discord bot and one dashboard per host: a second bot would post every
# message twice and a second dashboard would fight for the same port.
SINGLETON_UNITS=("v3xctrl-relay-bot.service" "v3xctrl-relay-stats.service")

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "${SCRIPT_DIRECTORY}/../.." && pwd)"

usage() {
  cat >&2 <<USAGE
Usage:
  install.sh base [--python PATH] [--root PATH] [--name NAME]
                                          install units, user, state directory, config
  install.sh add <instance> [--name NAME]     enable one relay instance
  install.sh remove <instance> [--name NAME]  disable and stop one relay instance

  --python  interpreter the services run (default: the python3 on PATH)
  --root    source tree the services run from (default: ${SOURCE_ROOT})
  --name    deployment name, for a second set of units beside production,
            for example --name dev with --root /opt/v3xctrl-dev. Their units
            are v3xctrl-relay-NAME.target and v3xctrl-relay-NAME-server@.
USAGE
  exit 2
}

set_deployment_name() {
  local name="${1:-}"

  if [[ ! "${name}" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; then
    echo "A deployment name holds lowercase letters, digits and dashes: '${name}'" >&2
    exit 1
  fi

  deployment_name="${name}"
}

# Installed name of a unit shipped in systemd/, prefixed for a named deployment.
installed_name() {
  local base="$1"

  if [[ -z "${deployment_name}" ]]; then
    echo "${base}"
  else
    echo "v3xctrl-relay-${deployment_name}${base#v3xctrl-relay}"
  fi
}

target_unit() {
  installed_name "v3xctrl-relay.target"
}

instance_unit() {
  local template
  template="$(installed_name "v3xctrl-relay-server@.service")"
  echo "${template/@.service/@${1}.service}"
}

is_singleton() {
  local base="$1" singleton
  for singleton in "${SINGLETON_UNITS[@]}"; do
    if [[ "${base}" == "${singleton}" ]]; then
      return 0
    fi
  done

  return 1
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
      --name) set_deployment_name "${2:-}"; shift 2 ;;
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

  local unit source_base installed
  local written=()
  for unit in "${SCRIPT_DIRECTORY}"/systemd/*; do
    source_base="$(basename "${unit}")"

    if [[ -n "${deployment_name}" ]] && is_singleton "${source_base}"; then
      continue
    fi

    installed="$(installed_name "${source_base}")"
    sed -e "s|@PYTHON@|${python_path}|g" -e "s|@ROOT@|${root_path}|g" \
      -e "s|@TARGET@|$(target_unit)|g" \
      "${unit}" >"${UNIT_DIRECTORY}/${installed}"
    written+=("${UNIT_DIRECTORY}/${installed}")
  done
  chmod 0644 "${written[@]}"

  systemctl daemon-reload

  # Enabling the singletons here is what links them into the production target.
  # Relay instances are enabled one at a time by "add", since their number is a
  # per-host decision.
  if [[ -z "${deployment_name}" ]]; then
    systemctl enable "$(target_unit)" v3xctrl-relay-bot.service v3xctrl-relay-stats.service >/dev/null
  else
    systemctl enable "$(target_unit)" >/dev/null
  fi

  echo "Installed $(target_unit) and its units, running ${python_path} from ${root_path}"
  echo "Next: fill in ${CONFIG_PATH}, then install.sh add <instance>${deployment_name:+ --name ${deployment_name}}"
}

add_instance() {
  local instance=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name) set_deployment_name "${2:-}"; shift 2 ;;
      -*) usage ;;
      *) instance="$1"; shift ;;
    esac
  done

  [[ -n "${instance}" ]] || usage

  local unit
  unit="$(instance_unit "${instance}")"

  if [[ ! -e "${UNIT_DIRECTORY}/$(installed_name "v3xctrl-relay-server@.service")" ]]; then
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
  local instance=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name) set_deployment_name "${2:-}"; shift 2 ;;
      -*) usage ;;
      *) instance="$1"; shift ;;
    esac
  done

  [[ -n "${instance}" ]] || usage

  local unit
  unit="$(instance_unit "${instance}")"

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
