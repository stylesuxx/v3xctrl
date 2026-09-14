"""Typed sections of the viewer configuration.

Every section is frozen, so a module can hold one without another module's edit
reaching it, and every default lives on exactly one field.

Parsing is also where a malformed value is caught. A value whose type does not
match its field falls back to that field's default and is reported, so a single
bad key in a hand-edited config file leaves the viewer running.
"""

import logging
from dataclasses import dataclass, fields
from enum import Enum, StrEnum
from typing import Any, ClassVar, Self

from v3xctrl_tcp import Transport

logger = logging.getLogger(__name__)

DEFAULT_TRANSPORT = Transport.UDP


class VideoReceiver(StrEnum):
    AUTO = "auto"
    GST = "gst"
    PYAV = "pyav"


def coerce(location: str, value: Any, default: Any) -> Any:
    """Return value if it fits the default's type, otherwise the default.

    Args:
        location: Dotted config path, used to name the key in a warning
        value: Raw value as it came out of the config file
        default: Value to fall back to, whose type sets what is accepted
    """
    match default:
        case Enum():
            try:
                return type(default)(value)
            except ValueError:
                accepted = ", ".join(member.value for member in type(default))
                logger.warning(f"{location}: {value!r} is not one of {accepted}. Using {default.value!r}.")

                return default

        case bool():
            if isinstance(value, bool):
                return value

        case int():
            # bool subclasses int, so a flag in a number's place is a mistake
            if isinstance(value, int) and not isinstance(value, bool):
                return value

        case _:
            if isinstance(value, type(default)):
                return value

    logger.warning(f"{location}: expected {type(default).__name__}, got {value!r}. Using {default!r}.")

    return default


@dataclass(frozen=True, slots=True)
class Section:
    """A group of configuration keys that travels as one immutable value."""

    NAME: ClassVar[str] = ""

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Self:
        """Build a section from a raw config table, filling in missing keys."""
        defaults = cls()
        values = {}

        for field in fields(cls):
            if field.name in raw:
                location = f"{cls.NAME}.{field.name}"
                values[field.name] = coerce(location, raw[field.name], getattr(defaults, field.name))

        return cls(**values)

    def to_raw(self) -> dict[str, Any]:
        """Render the section back into the shape the config file holds."""
        raw: dict[str, Any] = {}

        for field in fields(self):
            value = getattr(self, field.name)
            raw[field.name] = value.value if isinstance(value, Enum) else value

        return raw


@dataclass(frozen=True, slots=True)
class PortSettings(Section):
    NAME: ClassVar[str] = "ports"

    video: int = 16384
    control: int = 16386


@dataclass(frozen=True, slots=True)
class RelaySettings(Section):
    NAME: ClassVar[str] = "relay"

    enabled: bool = False
    server: str = "relay.v3xctrl.com:8888"
    id: str = "test123"
    spectator_mode: bool = False


@dataclass(frozen=True, slots=True)
class TimingSettings(Section):
    NAME: ClassVar[str] = "timing"

    main_loop_fps: int = 60
    control_update_hz: int = 30
    latency_check_hz: int = 1


@dataclass(frozen=True, slots=True)
class VideoSettings(Section):
    NAME: ClassVar[str] = "video"

    width: int = 1280
    height: int = 720
    fullscreen: bool = False
    render_ratio: int = 0
    receiver: VideoReceiver = VideoReceiver.AUTO
