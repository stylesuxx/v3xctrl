import copy
from pathlib import Path
import pygame
import tomllib
import tomli_w


class Settings:
    DEFAULTS = {
        "controls": {
          "keyboard": {
              "throttle_up": pygame.K_w,
              "throttle_down": pygame.K_s,
              "steering_left": pygame.K_a,
              "steering_right": pygame.K_d,
          }
        },
        "ports": {
            "video": 6666,
            "control": 6668,
        },
        "video": {
            "width": 1280,
            "height": 720,
        },
        "debug": True,
        "fps": 60,
        "widgets": {
            "fps": {
                "width": 100,
                "height": 75,
                "average_window": 30,
                "graph_frames": 300,
            }
        },
        "settings": {
            "title": "RC - Streamer",
            "throttle": {
                "step": 0.02,
                "friction": 0.01,
            },
            "steering": {
                "step": 0.05,
                "friction": 0.02,
            },
        },
    }

    def __init__(self, path: str):
        self.path = Path(path)
        self.settings = {}
        self.load()

    def load(self):
        if self.path.exists():
            with self.path.open("rb") as file:
                raw = tomllib.load(file)
                loaded = self._deserialize(raw)
                self.settings = self._merge(copy.deepcopy(self.DEFAULTS), loaded)
        else:
            self.settings = copy.deepcopy(self.DEFAULTS)

    def save(self):
        serialized = self._serialize(self.settings)
        with self.path.open("wb") as f:
            f.write(tomli_w.dumps(serialized).encode("utf-8"))

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value

    def delete(self, key):
        if key in self.settings:
            del self.settings[key]

    def _merge(self, base, override):
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

    def _serialize(self, data):
        if "controls" in data:
            data = data.copy()
            data["controls"] = self._serialize_controls(data["controls"])

        return data

    def _deserialize(self, data):
        if "controls" in data:
            data = data.copy()
            data["controls"] = self._deserialize_controls(data["controls"])

        return data

    def _serialize_controls(self, controls):
        return {
            device: {k: self._key_to_string(v) for k, v in bindings.items()}
            for device, bindings in controls.items()
        }

    def _deserialize_controls(self, controls):
        return {
            device: {k: self._string_to_key(v) for k, v in bindings.items()}
            for device, bindings in controls.items()
        }

    def _key_to_string(self, keycode):
        for name in dir(pygame):
            if name.startswith("K_") and getattr(pygame, name) == keycode:
                return name

        raise ValueError(f"Unknown key code: {keycode}")

    def _string_to_key(self, keyname):
        try:
            return getattr(pygame, keyname)
        except AttributeError:
            raise ValueError(f"Invalid key name in config: {keyname}")
