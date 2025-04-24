import pygame
import threading
from typing import Callable, List, Optional, Dict


class GamepadManager:
    REFRESH_INTERVAL_MS = 1000

    def __init__(self):
        pygame.joystick.init()

        self._lock = threading.Lock()
        self._gamepads: List[pygame.joystick.Joystick] = []
        self._selected_index: int = 0
        self._settings: Dict[str, dict] = {}  # Calibration/settings per GUID
        self._observers: List[Callable[[List[pygame.joystick.Joystick]], None]] = []

        self._active_guid: Optional[str] = None
        self._active_gamepad: Optional[pygame.joystick.Joystick] = None
        self._active_settings: Optional[dict] = None

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._background_loop, daemon=True)
        self._thread.start()

    def _background_loop(self):
        while not self._stop_event.is_set():
            gamepads = []
            for i in range(pygame.joystick.get_count()):
                try:
                    js = pygame.joystick.Joystick(i)
                    if not js.get_init():
                        js.init()
                    gamepads.append(js)
                except pygame.error:
                    continue

            with self._lock:
                changed = self._gamepads_changed(gamepads)
                if changed:
                    self._gamepads = gamepads
                    self._selected_index = min(self._selected_index, len(gamepads) - 1)
                observers = list(self._observers)

            for cb in observers:
                cb(gamepads)

            pygame.time.wait(self.REFRESH_INTERVAL_MS)

    def _gamepads_changed(self, new_gamepads: List[pygame.joystick.Joystick]) -> bool:
        return (
            len(new_gamepads) != len(self._gamepads) or
            any(a.get_instance_id() != b.get_instance_id() for a, b in zip(new_gamepads, self._gamepads))
        )

    def add_observer(self, callback: Callable[[List[pygame.joystick.Joystick]], None]):
        with self._lock:
            self._observers.append(callback)

    def get_gamepads(self) -> List[pygame.joystick.Joystick]:
        return list(self._gamepads)

    def get_selected_gamepad(self) -> Optional[pygame.joystick.Joystick]:
        with self._lock:
            if 0 <= self._selected_index < len(self._gamepads):
                return self._gamepads[self._selected_index]
            return None

    def get_selected_index(self) -> int:
        return self._selected_index

    def set_selected_index(self, index: int):
        with self._lock:
            self._selected_index = index

    def set_calibration(self, guid: str, settings: dict):
        with self._lock:
            self._settings[guid] = settings

    def get_calibration(self, guid: str) -> Optional[dict]:
        return self._settings.get(guid)

    def set_active(self, guid: str):
        with self._lock:
            js = next((j for j in self._gamepads if j.get_guid() == guid), None)
            settings = self._settings.get(guid)

            self._active_guid = None
            self._active_gamepad = None
            self._active_settings = None
            if js and settings:
                if not js.get_init():
                    js.init()
                self._active_guid = guid
                self._active_gamepad = js
                self._active_settings = settings

    def read_inputs(self) -> Optional[Dict[str, float]]:
        js, settings = self._active_gamepad, self._active_settings
        if not js or not js.get_init() or not settings:
            return None

        pygame.event.pump()
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
        self._thread.join()
