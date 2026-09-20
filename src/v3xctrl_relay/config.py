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


def get_section(config: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: dict[str, Any] = config

    for index, key in enumerate(keys):
        value = current.get(key)
        if value is None:
            return {}

        if not isinstance(value, dict):
            path = ".".join(keys[: index + 1])
            raise ConfigError(f"'{path}' must be a table, got {type(value).__name__}")

        current = value

    return current


def require(value: Any, name: str, argument: str) -> Any:
    if value is None:
        raise ConfigError(f"{name} is not set: pass {argument} or set it in the configuration file")

    return value
