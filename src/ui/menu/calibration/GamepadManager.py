import pygame
import threading
from typing import Callable, List


class GamepadManager:
    REFRESH_INTERVAL_MS = 1000

    def __init__(self):
        pygame.joystick.init()

        self._lock = threading.Lock()
        self._gamepads: List[pygame.joystick.Joystick] = []
        self._selected_index: int = 0
        self._observers: List[Callable[[List[pygame.joystick.Joystick]], None]] = []

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

    def get_selected_index(self) -> int:
        with self._lock:
            return self._selected_index

    def set_selected_index(self, index: int):
        with self._lock:
            self._selected_index = index

    def stop(self):
        self._stop_event.set()
        self._thread.join()
