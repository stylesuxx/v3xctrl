import tomllib
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = "/etc/v3xctrl/relay.toml"


class ConfigError(Exception): ...


def load(path: str | Path) -> dict[str, Any]:
    """
    A missing file yields an empty configuration, so running without one falls
    back to command line arguments and built-in defaults.
    """
    config_path = Path(path)

    try:
        with config_path.open("rb") as handle:
            return tomllib.load(handle)

    except FileNotFoundError:
        return {}

    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{config_path}: {e}") from e

    except OSError as e:
        raise ConfigError(f"{config_path}: {e}") from e


def get_section(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise ConfigError(f"'{key}' must be a table, got {type(value).__name__}")

    return value


def get_relay_ports(stats: dict[str, Any]) -> list[int]:
    configured = stats.get("relay_ports")
    if configured is None:
        return []

    if not isinstance(configured, list):
        raise ConfigError("'stats.relay_ports' must be a list of port numbers")

    ports = []
    for entry in configured:
        if isinstance(entry, bool) or not isinstance(entry, int):
            raise ConfigError(f"'stats.relay_ports' contains a non-numeric entry: {entry!r}")

        ports.append(entry)

    return ports
