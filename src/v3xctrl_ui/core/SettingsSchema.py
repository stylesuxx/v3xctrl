"""Typed sections of the viewer configuration.

Every section is frozen, so a module can hold one without another module's edit
reaching it, and every default lives on exactly one field.

Parsing is also where a malformed value is caught. A value whose type does not
match its field falls back to that field's default and is reported, so a single
bad key in a hand-edited config file leaves the viewer running.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from enum import Enum, StrEnum
from typing import Any, ClassVar, Self

import pygame

from v3xctrl_tcp import Transport

logger = logging.getLogger(__name__)

DEFAULT_TRANSPORT = Transport.UDP


class WidgetAlignment(StrEnum):
    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"
    BOTTOM_CENTER = "bottom-center"


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

        case tuple():
            # TOML has arrays, not tuples, so a fixed-length pair arrives as a list
            if isinstance(value, list | tuple) and len(value) == len(default):
                return tuple(value)

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

        for section_field in fields(cls):
            if section_field.name in raw:
                location = f"{cls.NAME}.{section_field.name}"
                values[section_field.name] = coerce(
                    location, raw[section_field.name], getattr(defaults, section_field.name)
                )

        return cls(**values)

    def to_raw(self) -> dict[str, Any]:
        """Render the section back into the shape the config file holds."""
        raw: dict[str, Any] = {}

        for section_field in fields(self):
            raw[section_field.name] = _to_toml(getattr(self, section_field.name))

        return raw


def key_name_for(key_code: int) -> str:
    for name in dir(pygame):
        if name.startswith("K_") and getattr(pygame, name) == key_code:
            return name

    raise ValueError(f"Unknown key code: {key_code}")


def key_code_for(location: str, key_name: Any, default: int) -> int:
    if isinstance(key_name, str):
        key_code = getattr(pygame, key_name, None)
        if isinstance(key_code, int):
            return key_code

    logger.warning(f"{location}: {key_name!r} is not a pygame key name. Using {key_name_for(default)!r}.")

    return default


def _to_toml(value: Any) -> Any:
    match value:
        case Enum():
            return value.value

        case tuple():
            return list(value)

        case _:
            return value


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
    id: str = ""
    spectator_mode: bool = False


@dataclass(frozen=True, slots=True)
class TimingSettings(Section):
    NAME: ClassVar[str] = "timing"

    main_loop_fps: int = 60
    control_update_hz: int = 30
    latency_check_hz: int = 1


@dataclass(frozen=True, slots=True)
class WidgetConfig(Section):
    NAME: ClassVar[str] = "widgets"

    display: bool = False
    align: WidgetAlignment = WidgetAlignment.TOP_LEFT
    offset: tuple[int, int] = (0, 0)
    padding: int = 0


@dataclass(frozen=True, slots=True)
class FpsGraphConfig(Section):
    NAME: ClassVar[str] = "widgets.fps"

    width: int = 100
    height: int = 75


@dataclass(frozen=True, slots=True)
class WidgetSettings(Section):
    """Widget configuration, keyed by widget or group name.

    The `fps` key holds graph dimensions rather than placement, so it is parsed
    into its own type and kept out of the mapping.
    """

    NAME: ClassVar[str] = "widgets"

    FPS_KEY: ClassVar[str] = "fps"

    DEFAULT_CONFIGS: ClassVar[Mapping[str, WidgetConfig]] = {
        "debug": WidgetConfig(display=False, offset=(10, 10), padding=5),
        "debug_fps_loop": WidgetConfig(display=True),
        "debug_fps_video": WidgetConfig(display=True),
        "debug_data": WidgetConfig(display=True),
        "debug_latency": WidgetConfig(display=True),
        "steering": WidgetConfig(display=True, align=WidgetAlignment.BOTTOM_CENTER, offset=(10, 0)),
        "throttle": WidgetConfig(display=True, align=WidgetAlignment.BOTTOM_LEFT, offset=(10, 10)),
        "signal": WidgetConfig(display=True, align=WidgetAlignment.TOP_RIGHT, offset=(10, 10)),
        "signal_quality": WidgetConfig(display=True),
        "signal_band": WidgetConfig(display=True),
        "signal_cell": WidgetConfig(display=False),
        "battery": WidgetConfig(display=True, align=WidgetAlignment.TOP_RIGHT, offset=(105, 10)),
        "battery_icon": WidgetConfig(display=True),
        "battery_voltage": WidgetConfig(display=True),
        "battery_average_voltage": WidgetConfig(display=True),
        "battery_percent": WidgetConfig(display=True),
        "battery_current": WidgetConfig(display=False),
        "rec": WidgetConfig(display=True, align=WidgetAlignment.BOTTOM_RIGHT, offset=(10, 10)),
        "clock": WidgetConfig(display=False, align=WidgetAlignment.BOTTOM_RIGHT),
        "gps": WidgetConfig(display=True, align=WidgetAlignment.TOP_RIGHT, offset=(248, 10)),
        "gps_icon": WidgetConfig(display=True),
        "gps_fix": WidgetConfig(display=True),
        "gps_satellites": WidgetConfig(display=True),
        "gps_speed": WidgetConfig(display=True),
    }

    configs: Mapping[str, WidgetConfig] = field(default_factory=lambda: dict(WidgetSettings.DEFAULT_CONFIGS))
    fps: FpsGraphConfig = field(default_factory=FpsGraphConfig)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Self:
        configs = dict(cls.DEFAULT_CONFIGS)
        for name, table in raw.items():
            if name != cls.FPS_KEY:
                configs[name] = cls._config_from_raw(name, table)

        return cls(configs=configs, fps=FpsGraphConfig.from_raw(raw.get(cls.FPS_KEY, {})))

    @classmethod
    def _config_from_raw(cls, name: str, raw: dict[str, Any]) -> WidgetConfig:
        """Lay one widget's configured keys over that widget's own defaults.

        Keys the file leaves out keep the default for *this* widget, so hiding
        the steering indicator does not also move it to the top left.
        """
        base = cls.DEFAULT_CONFIGS.get(name, WidgetConfig())
        values = {}

        for widget_field in fields(WidgetConfig):
            if widget_field.name in raw:
                location = f"{cls.NAME}.{name}.{widget_field.name}"
                values[widget_field.name] = coerce(location, raw[widget_field.name], getattr(base, widget_field.name))

        return replace(base, **values)

    def to_raw(self) -> dict[str, Any]:
        raw: dict[str, Any] = {name: config.to_raw() for name, config in self.configs.items()}
        raw[self.FPS_KEY] = self.fps.to_raw()

        return raw

    def get(self, name: str) -> WidgetConfig | None:
        return self.configs.get(name)

    def with_display(self, name: str, display: bool) -> "WidgetSettings":
        config = self.configs.get(name, WidgetConfig())

        return replace(self, configs={**self.configs, name: replace(config, display=display)})


@dataclass(frozen=True, slots=True)
class KeyboardControls(Section):
    """Key bindings, held as pygame keycodes.

    The config file stores pygame key names (`K_w`) rather than the numbers they
    stand for, so that a binding survives a pygame version that renumbers them.
    """

    NAME: ClassVar[str] = "controls.keyboard"

    throttle_up: int = pygame.K_w
    throttle_down: int = pygame.K_s
    steering_left: int = pygame.K_a
    steering_right: int = pygame.K_d
    trim_increase: int = pygame.K_RIGHT
    trim_decrease: int = pygame.K_LEFT
    rec_toggle: int = pygame.K_r

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Self:
        defaults = cls()
        values = {}

        for control_field in fields(cls):
            if control_field.name in raw:
                location = f"{cls.NAME}.{control_field.name}"
                default = getattr(defaults, control_field.name)
                values[control_field.name] = key_code_for(location, raw[control_field.name], default)

        return cls(**values)

    def to_raw(self) -> dict[str, Any]:
        return {control_field.name: key_name_for(getattr(self, control_field.name)) for control_field in fields(self)}


@dataclass(frozen=True, slots=True)
class ControlSettings(Section):
    NAME: ClassVar[str] = "controls"

    keyboard: KeyboardControls = field(default_factory=KeyboardControls)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Self:
        return cls(keyboard=KeyboardControls.from_raw(raw.get("keyboard", {})))

    def to_raw(self) -> dict[str, Any]:
        return {"keyboard": self.keyboard.to_raw()}


@dataclass(frozen=True, slots=True)
class InputSettings(Section):
    NAME: ClassVar[str] = "input"

    guid: str = ""


@dataclass(frozen=True, slots=True)
class CalibrationSettings(Section):
    """Recorded gamepad calibrations, keyed by device GUID.

    These are recorded by the calibration widget rather than configured, so
    there is nothing to default and no schema to enforce. The inner shape
    belongs to the gamepad subsystem, which both writes and reads it; this
    section exists so the data is declared and round-trips rather than living
    in an untyped leftover.
    """

    NAME: ClassVar[str] = "calibrations"

    by_guid: Mapping[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Self:
        return cls(by_guid=dict(raw))

    def to_raw(self) -> dict[str, Any]:
        return dict(self.by_guid)


@dataclass(frozen=True, slots=True)
class VideoSettings(Section):
    NAME: ClassVar[str] = "video"

    width: int = 1280
    height: int = 720
    fullscreen: bool = False
    render_ratio: int = 0
    receiver: VideoReceiver = VideoReceiver.AUTO
