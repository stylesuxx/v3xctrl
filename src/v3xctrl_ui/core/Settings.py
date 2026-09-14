import copy
import tomllib
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

import pygame
import tomli_w
from platformdirs import user_config_dir

from v3xctrl_ui.core.SettingsSchema import (
    DEFAULT_TRANSPORT,
    PortSettings,
    RelaySettings,
    Section,
    TimingSettings,
    VideoSettings,
    WidgetSettings,
    coerce,
)


class Settings:
    """The viewer configuration, as typed sections over a TOML file.

    Sections listed in SECTIONS are parsed once at load and handed out as frozen
    values. Keys that have not been given a section yet stay in the `settings`
    dict, and `get`/`set` cover both, so a caller can move to a section at its
    own pace.
    """

    SECTIONS: ClassVar[dict[str, type[Section]]] = {
        "ports": PortSettings,
        "relay": RelaySettings,
        "timing": TimingSettings,
        "video": VideoSettings,
        "widgets": WidgetSettings,
    }

    # Top-level keys that hold one value rather than a table, mapped to their default
    SCALARS: ClassVar[dict[str, Any]] = {
        "transport": DEFAULT_TRANSPORT,
        "udp_packet_ttl": 100,
        "control_buffer_capacity": 1,
        "debug": True,
        "show_connection_info": True,
    }

    DEFAULTS: ClassVar[dict[str, Any]] = {
        "controls": {
            "keyboard": {
                "throttle_up": pygame.K_w,
                "throttle_down": pygame.K_s,
                "steering_left": pygame.K_a,
                "steering_right": pygame.K_d,
                "trim_increase": pygame.K_RIGHT,
                "trim_decrease": pygame.K_LEFT,
                "rec_toggle": pygame.K_r,
            }
        },
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
                loaded = self._deserialize(tomllib.load(file))

        merged = self._merge(copy.deepcopy(self.DEFAULTS), loaded)

        for key, section in self.SECTIONS.items():
            setattr(self, key, section.from_raw(merged.pop(key, {})))

        for key, default in self.SCALARS.items():
            setattr(self, key, coerce(key, merged.pop(key, default), default))

        self.settings = merged

    def save(self) -> None:
        serialized = self._serialize({**self.settings, **self._sections_to_raw()})
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

    def _merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        for key, value in override.items():
            match base.get(key), value:
                case dict() as existing, dict():
                    base[key] = self._merge(existing, value)

                case _:
                    base[key] = value

        return base

    def _serialize(self, data: dict[str, Any]) -> dict[str, Any] | list[Any]:
        if "controls" in data:
            data = data.copy()
            data["controls"] = self._serialize_controls(data["controls"])

        return self._remove_none(data)

    def _remove_none(self, obj: object) -> dict[str, Any] | list[Any] | object:
        match obj:
            case dict():
                return {key: self._remove_none(value) for key, value in obj.items() if value is not None}

            case list():
                return [self._remove_none(value) for value in obj if value is not None]

            case _:
                return obj

    def _deserialize(self, data: dict[str, Any]) -> dict[str, Any]:
        if "controls" in data:
            data = data.copy()
            data["controls"] = self._deserialize_controls(data["controls"])

        return data

    def _serialize_controls(self, controls: dict[str, Any]) -> dict[str, Any]:
        """Turn each device's keycodes into the pygame key names the file holds."""
        serialized: dict[str, Any] = {}

        for device, bindings in controls.items():
            key_names: dict[str, str] = {}
            for control, keycode in bindings.items():
                key_names[control] = self._key_to_string(keycode)

            serialized[device] = key_names

        return serialized

    def _deserialize_controls(self, controls: dict[str, Any]) -> dict[str, Any]:
        """Turn each device's key names back into the keycodes pygame compares against."""
        deserialized: dict[str, Any] = {}

        for device, bindings in controls.items():
            keycodes: dict[str, int] = {}
            for control, key_name in bindings.items():
                keycodes[control] = self._string_to_key(key_name)

            deserialized[device] = keycodes

        return deserialized

    def _key_to_string(self, keycode: Any) -> str:
        for name in dir(pygame):
            if name.startswith("K_") and getattr(pygame, name) == keycode:
                return name

        raise ValueError(f"Unknown key code: {keycode}")

    def _string_to_key(self, key_name: str) -> int:
        try:
            keycode: int = getattr(pygame, key_name)
        except AttributeError:
            raise ValueError(f"Invalid key name in config: {key_name}") from None

        return keycode
