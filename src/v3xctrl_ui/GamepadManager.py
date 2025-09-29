"""
GamepadManager does what the name implies:
* Checks for new gampepads regularly
* Updates the list of active gamepads
* Updates the list of active settings
* Notifies observers when the list of gamepads or settings changes

One gamepad can be active at a time, but there can be multiple gamepads
connected. The manager will provide you with the latest input reads from the
active gampad, normalized based on the calibration.

NOTE: Make sure to add observers before starting the GampadManager, otherwise
      you might miss the first update.
"""
import logging
import threading
from typing import Callable, List, Optional, Dict, Set, Tuple, Any

import pygame
from pygame.joystick import JoystickType

from v3xctrl_helper import clamp


class GamepadManager(threading.Thread):
    REFRESH_INTERVAL_MS = 1000

    def __init__(self) -> None:
        super().__init__(daemon=True)
        pygame.joystick.init()

        self._lock = threading.Lock()
        self._gamepads: Dict[str, JoystickType] = {}
        self._settings: Dict[str, Any] = {}  # Calibration/settings per GUID
        self._observers: List[Callable[[Dict[str, JoystickType]], None]] = []

        self._active_guid: Optional[str] = None
        self._active_gamepad: Optional[JoystickType] = None
        self._active_settings: Optional[Dict[str, Any]] = None

        self._previous_guids: Set[str] = set()

        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            gamepads: Dict[str, JoystickType] = {}
            for i in range(pygame.joystick.get_count()):
                try:
                    js = pygame.joystick.Joystick(i)
                    guid = js.get_guid()

                    if guid not in gamepads:
                        gamepads[guid] = js

                except pygame.error:
                    continue

            guids = set(gamepads.keys())
            if guids != self._previous_guids:
                logging.info("New gamepad detected")

                with self._lock:
                    self._gamepads = gamepads
                    self._previous_guids = guids

                    """
                    If the default gamepad (according to setting) is available,
                    use it.
                    """
                    if self._active_guid and gamepads.get(self._active_guid):
                        if not self._active_gamepad or not self._active_settings:
                            self._set_active_unlocked(self._active_guid)
                            logging.info("Found default gamepad")
                    else:
                        """
                        Check if another gamepad for which we have a
                        configuration is available, if so, use the first
                        matching one.
                        """
                        for id in guids:
                            if id in self._settings:
                                if (
                                    not self._active_gamepad or
                                    not self._active_settings
                                ):
                                    self._set_active_unlocked(id)
                                    logging.info("Found gamepad with calibration")
                                    break

                    if not self._active_gamepad or not self._active_settings:
                        self._active_gamepad = None
                        self._active_settings = None

                    observers = list(self._observers)

                for cb in observers:
                    cb(gamepads)

            pygame.time.wait(self.REFRESH_INTERVAL_MS)

    def add_observer(
        self,
        callback: Callable[[Dict[str, JoystickType]], None]
    ) -> None:
        with self._lock:
            self._observers.append(callback)

    def get_gamepads(self) -> Dict[str, JoystickType]:
        return self._gamepads

    def get_gamepad(self, guid: str) -> JoystickType:
        return self._gamepads[guid]

    def set_calibration(self, guid: str, settings: Dict[str, Any]) -> None:
        with self._lock:
            self._settings[guid] = settings

    def get_calibrations(self) -> Dict[str, Any]:
        return self._settings

    def get_calibration(self, guid: str) -> Dict[str, Any]:
        return self._settings.get(guid, {})

    def set_active(self, guid: str) -> None:
        with self._lock:
            self._set_active_unlocked(guid)

    def read_inputs(self) -> Optional[Dict[str, float]]:
        with self._lock:
            js = self._active_gamepad
            settings = self._active_settings

        if not js or not js.get_init() or not settings:
            return None

        values: Dict[str, float] = {}
        for key, cfg in settings.items():
            axis = cfg.get("axis")
            if axis is not None and 0 <= axis < js.get_numaxes():
                try:
                    raw = js.get_axis(axis)
                    normalized = 0

                    invert = cfg.get("invert")
                    min_cal = cfg.get("min")
                    max_cal = cfg.get("max")
                    raw = clamp(raw, min_cal, max_cal)

                    center_cal = cfg.get("center", None)
                    if center_cal is not None:
                        cal = (min_cal, center_cal, max_cal)
                        out = (-1.0, 0.0, 1.0)

                        normalized = self._remap_centered(raw, cal, out)
                        if invert:
                            normalized = -normalized
                    else:
                        if invert:
                            min_cal, max_cal = max_cal, min_cal
                        cal = (min_cal, max_cal)
                        out = (0.0, 1.0)
                        normalized = self._remap(raw, cal, out)

                    values[key] = normalized
                except pygame.error:
                    continue

        return values

    def stop(self) -> None:
        self._stop_event.set()

    def _set_active_unlocked(self, guid: str) -> None:
        self._active_guid = guid

        js = self._gamepads.get(self._active_guid)
        settings = self._settings.get(self._active_guid)

        self._active_gamepad = None
        self._active_settings = None
        if js and settings:
            self._active_gamepad = js
            self._active_settings = settings

    def _remap_centered(
        self,
        value: float,
        calibrated: Tuple[float, float, float],
        normalized: Tuple[float, float, float]
    ) -> float:
        in_min, in_center, in_max = calibrated
        out_min, out_center, out_max = normalized
        if value < in_center:
            in_span = in_center - in_min
            out_span = out_center - out_min

            if in_span == 0:
                return 0

            scale = (value - in_min) / in_span

            return out_min + out_span * scale
        else:
            in_span = in_max - in_center
            out_span = out_max - out_center

            if in_span == 0:
                return 0

            scale = (value - in_center) / in_span

            return out_center + scale * out_span

    def _remap(
        self,
        value: float,
        calibrated: Tuple[float, float],
        normalized: Tuple[float, float]
    ) -> float:
        in_min, in_max = calibrated
        out_min, out_max = normalized
        in_span = in_max - in_min
        out_span = out_max - out_min

        if in_span == 0:
            return 0

        scale = (value - in_min) / in_span

        return out_min + scale * out_span
