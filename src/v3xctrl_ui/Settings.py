from typing import Dict, List, Any
from pathlib import Path
import copy

import tomllib
import tomli_w

import pygame


class Settings:
    DEFAULTS: Dict[str, Any] = {
        "controls": {
          "keyboard": {
              "throttle_up": pygame.K_w,
              "throttle_down": pygame.K_s,
              "steering_left": pygame.K_a,
              "steering_right": pygame.K_d,
          }
        },
        "relay": {
            "enabled": False,
            "server": "rendezvous.websium.at:8888",
            "id": "test123"
        },
        "ports": {
            "video": 6666,
            "control": 6668,
        },
        "video": {
            "width": 1280,
            "height": 720,
            "fullscreen": False,
        },
        "udp_packet_ttl": 100,
        "debug": True,
        "show_connection_info": True,
        "timing": {
            "main_loop_fps": 60,
            "control_update_hz": 30,
            "latency_check_hz": 1,
        },
        "widgets": {
            "debug": {
                "display": True,
                "align": "top-left",
                "offset": [10, 10],
                "padding": 5
            },
            "debug_fps_loop": {
                "display": True
            },
            "debug_fps_video": {
                "display": True
            },
            "debug_data": {
                "display": True
            },
            "debug_latency": {
                "display": True
            },
            "fps": {
                "width": 100,
                "height": 75,
                "average_window": 30,
                "graph_frames": 300,
            },
            "steering": {
                "display": True,
                "align": "bottom-center",
                "offset": [10, 0]
            },
            "throttle": {
                "display": True,
                "align": "bottom-left",
                "offset": [10, 10]
            },
            "signal": {
                "display": True,
                "align": "top-right",
                "offset": [10, 10],
                "padding": 0,
            },
            "signal_quality": {
                "display": True
            },
            "signal_band": {
                "display": True
            },
            "battery": {
                "display": True,
                "align": "top-right",
                "offset": [78, 10]
            },
            "battery_icon": {
                "display": True
            },
            "battery_voltage": {
                "display": True
            },
            "battery_average_voltage": {
                "display": True
            },
            "battery_percent": {
                "display": True
            },
        },
        "settings": {
            "title": "V3XCTRL",
            "throttle": {
                "step": 0.1,
                "friction": 0.2,
            },
            "steering": {
                "step": 0.1,
                "friction": 0.2,
            },
        },
    }

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.settings = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            with self.path.open("rb") as file:
                raw = tomllib.load(file)
                loaded = self._deserialize(raw)
                self.settings = self._merge(copy.deepcopy(self.DEFAULTS), loaded)
        else:
            self.settings = copy.deepcopy(self.DEFAULTS)

    def save(self) -> None:
        serialized = self._serialize(self.settings)
        with self.path.open("wb") as f:
            f.write(tomli_w.dumps(serialized).encode("utf-8"))

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value

    def delete(self, key: str) -> None:
        if key in self.settings:
            del self.settings[key]

    def _merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in override.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                base[key] = self._merge(base[key], value)
            else:
                base[key] = value
        return base

    def _serialize(self, data: Dict[str, Any]) -> Dict[str, Any] | List[Any]:
        if "controls" in data:
            data = data.copy()
            data["controls"] = self._serialize_controls(data["controls"])
        return self._remove_none(data)

    def _remove_none(self, obj: object) -> Dict[str, Any] | List[Any] | object:
        if isinstance(obj, dict):
            return {k: self._remove_none(v) for k, v in obj.items() if v is not None}
        elif isinstance(obj, list):
            return [self._remove_none(v) for v in obj if v is not None]
        else:
            return obj

    def _deserialize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if "controls" in data:
            data = data.copy()
            data["controls"] = self._deserialize_controls(data["controls"])

        return data

    def _serialize_controls(self, controls: Dict[str, Any]) -> Dict[str, Any]:
        return {
            device: {k: self._key_to_string(v) for k, v in bindings.items()}
            for device, bindings in controls.items()
        }

    def _deserialize_controls(self, controls: Dict[str, Any]) -> Dict[str, Any]:
        return {
            device: {k: self._string_to_key(v) for k, v in bindings.items()}
            for device, bindings in controls.items()
        }

    def _key_to_string(self, keycode: Any) -> str:
        for name in dir(pygame):
            if name.startswith("K_") and getattr(pygame, name) == keycode:
                return name

        raise ValueError(f"Unknown key code: {keycode}")

    def _string_to_key(self, keyname: str) -> str:
        try:
            return getattr(pygame, keyname)
        except AttributeError:
            raise ValueError(f"Invalid key name in config: {keyname}")
