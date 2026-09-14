import logging
import tomllib
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

import tomli_w
from platformdirs import user_config_dir

from v3xctrl_ui.core.SettingsSchema import (
    DEFAULT_TRANSPORT,
    CalibrationSettings,
    ControlSettings,
    InputSettings,
    PortSettings,
    RelaySettings,
    Section,
    TimingSettings,
    VideoSettings,
    WidgetSettings,
    coerce,
)

logger = logging.getLogger(__name__)


class Settings:
    """The viewer configuration, as typed sections over a TOML file.

    Every key the viewer knows about is parsed once at load into a frozen
    section or a scalar, and handed out as that. A key the file carries but the
    viewer does not know is reported and kept, so a hand-edited addition is
    never silently dropped.
    """

    SECTIONS: ClassVar[dict[str, type[Section]]] = {
        "ports": PortSettings,
        "relay": RelaySettings,
        "timing": TimingSettings,
        "video": VideoSettings,
        "widgets": WidgetSettings,
        "controls": ControlSettings,
        "calibrations": CalibrationSettings,
        "input": InputSettings,
    }

    # Top-level keys that hold one value rather than a table, mapped to their default
    SCALARS: ClassVar[dict[str, Any]] = {
        "transport": DEFAULT_TRANSPORT,
        "udp_packet_ttl": 100,
        "control_buffer_capacity": 1,
        "debug": True,
        "show_connection_info": True,
    }

    def __init__(self, path: str | None = None) -> None:
        default_path = Path(user_config_dir("v3xctrl-viewer")) / "settings.toml"

        self.path = Path(path) if path is not None else default_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.settings: dict[str, Any] = {}
        self.ports = PortSettings()
        self.relay = RelaySettings()
        self.timing = TimingSettings()
        self.video = VideoSettings()
        self.widgets = WidgetSettings()
        self.controls = ControlSettings()
        self.calibrations = CalibrationSettings()
        self.input = InputSettings()
        self.transport = DEFAULT_TRANSPORT
        self.udp_packet_ttl = self.SCALARS["udp_packet_ttl"]
        self.control_buffer_capacity = self.SCALARS["control_buffer_capacity"]
        self.debug = self.SCALARS["debug"]
        self.show_connection_info = self.SCALARS["show_connection_info"]

        self.load()

        if not self.path.exists():
            self.save()

    def load(self) -> None:
        loaded: dict[str, Any] = {}
        if self.path.exists():
            with self.path.open("rb") as file:
                loaded = tomllib.load(file)

        for key, section in self.SECTIONS.items():
            setattr(self, key, section.from_raw(loaded.pop(key, {})))

        for key, default in self.SCALARS.items():
            setattr(self, key, coerce(key, loaded.pop(key, default), default))

        for key in loaded:
            logger.warning(f"{key}: not a setting this viewer knows. Leaving it in {self.path.name} untouched.")

        self.settings = loaded

    def save(self) -> None:
        serialized = self._remove_none({**self.settings, **self._sections_to_raw()})
        with self.path.open("wb") as f:
            f.write(tomli_w.dumps(serialized).encode("utf-8"))

    def get(self, key: str, default: Any = None) -> Any:
        match key:
            case _ if key in self.SCALARS:
                return getattr(self, key)

            case _ if key in self.SECTIONS:
                section: Section = getattr(self, key)
                return section.to_raw()

            case _:
                return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        match key:
            case _ if key in self.SCALARS:
                setattr(self, key, coerce(key, value, self.SCALARS[key]))

            case _ if key in self.SECTIONS:
                section_type = self.SECTIONS[key]
                parsed = value if isinstance(value, section_type) else section_type.from_raw(value)
                setattr(self, key, parsed)

            case _:
                self.settings[key] = value

    def delete(self, key: str) -> None:
        """Drop a key, which for anything typed means resetting it to its default."""
        match key:
            case _ if key in self.SCALARS:
                setattr(self, key, self.SCALARS[key])

            case _ if key in self.SECTIONS:
                setattr(self, key, self.SECTIONS[key]())

            case _:
                self.settings.pop(key, None)

    def _sections_to_raw(self) -> dict[str, Any]:
        raw: dict[str, Any] = {key: getattr(self, key).to_raw() for key in self.SECTIONS}

        for key in self.SCALARS:
            value = getattr(self, key)
            raw[key] = value.value if isinstance(value, Enum) else value

        return raw

    def _remove_none(self, obj: object) -> dict[str, Any] | list[Any] | object:
        match obj:
            case dict():
                return {key: self._remove_none(value) for key, value in obj.items() if value is not None}

            case list():
                return [self._remove_none(value) for value in obj if value is not None]

            case _:
                return obj
