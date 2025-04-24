import pygame
import threading
from typing import Callable, List, Optional, Dict


class GamepadManager(threading.Thread):
    REFRESH_INTERVAL_MS = 1000

    def __init__(self):
        super().__init__(daemon=True)
        pygame.joystick.init()

        self._lock = threading.Lock()
        self._gamepads: Dict[str, pygame.joystick.Joystick] = {}
        self._settings: Dict[str, dict] = {}  # Calibration/settings per GUID
        self._observers: List[Callable[[Dict[str, pygame.joystick.Joystick]], None]] = []

        self._active_guid: Optional[str] = None
        self._active_gamepad: Optional[pygame.joystick.Joystick] = None
        self._active_settings: Optional[dict] = None

        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            gamepads: Dict[str, pygame.joystick.Joystick] = {}
            for i in range(pygame.joystick.get_count()):
                try:
                    js = pygame.joystick.Joystick(i)
                    if not js.get_init():
                        js.init()
                    gamepads[js.get_guid()] = js
                except pygame.error:
                    continue

            guids = set(gamepads.keys())
            previous_guids = set(self._gamepads.keys())

            if guids != previous_guids:
                with self._lock:
                    self._gamepads = gamepads

                    # If active GUID still matches one of the new gamepads, rebind it
                    if self._active_guid:
                        matching = gamepads.get(self._active_guid)
                        if matching:
                            if not self._active_gamepad or not self._active_settings:
                                self._set_active_unlocked(self._active_guid)
                        else:
                            self._active_gamepad = None
                            self._active_settings = None

                    observers = list(self._observers)

                for cb in observers:
                    cb(gamepads)

            pygame.time.wait(self.REFRESH_INTERVAL_MS)

    def add_observer(self, callback: Callable[[List[pygame.joystick.Joystick]], None]):
        with self._lock:
            self._observers.append(callback)

    def get_gamepads(self) -> List[pygame.joystick.Joystick]:
        return self._gamepads

    def get_gamepad(self, guid: str) -> pygame.joystick.Joystick:
        return self._gamepads[guid]

    def set_calibration(self, guid: str, settings: dict):
        with self._lock:
            self._settings[guid] = settings

    def get_calibration(self, guid: str) -> Optional[dict]:
        return self._settings.get(guid)

    def set_active(self, guid: str):
        with self._lock:
            self._set_active_unlocked(guid)

    def _set_active_unlocked(self, guid: str):
        self._active_guid = guid

        js = self._gamepads.get(self._active_guid)
        settings = self._settings.get(self._active_guid)

        self._active_gamepad = None
        self._active_settings = None
        if js and settings:
            if not js.get_init():
                js.init()
            self._active_gamepad = js
            self._active_settings = settings

    def read_inputs(self) -> Optional[Dict[str, float]]:
        with self._lock:
            js = self._active_gamepad
            settings = self._active_settings

        if not js or not js.get_init() or not settings:
            return None

        values = {}
        for key, cfg in settings.items():
            axis = cfg.get("axis")
            if axis is not None and 0 <= axis < js.get_numaxes():
                try:
                    raw = js.get_axis(axis)
                    if cfg.get("invert"):
                        raw = -raw
                    min_val = cfg.get("min", -1)
                    max_val = cfg.get("max", 1)
                    norm = (raw - min_val) / (max_val - min_val) if max_val != min_val else 0.5
                    norm = max(0.0, min(1.0, norm))
                    values[key] = norm
                except pygame.error:
                    continue

        return values

    def stop(self):
        self._stop_event.set()
