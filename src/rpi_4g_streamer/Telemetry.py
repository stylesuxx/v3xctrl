"""
This class collects telemetry data, all fetching of telemetry data should happen
here.

The only public interface is the get_telemetry() method.
"""
from atlib import AIR780EU
import logging
from typing import Dict
import threading
import time


class Telemetry(threading.Thread):
    def __init__(self, modem: str = None):
        super().__init__(daemon=True)

        self.telemetry = {
            'sig': {
                'rsrq': 255,
                'rsrp': 255
            },
            'loc': {
                'lat': 0,
                'lng': 0,
            },
            'ina': {
                'vol': 0,
                'cur': 0
            }
        }

        self._running = threading.Event()
        self._lock = threading.Lock()
        try:
            self._modem = AIR780EU(modem) if modem else None
        except:
            logging.error("Failed to initialize modem!")

    def _update_signal(self) -> None:
        try:
            signal_quality = self._modem.get_signal_quality()
            with self._lock:
                self.telemetry['sig']['rsrq'] = signal_quality.rsrq
                self.telemetry['sig']['rsrp'] = signal_quality.rsrp
        except:
            self.telemetry['sig']['rsrq'] = 255
            self.telemetry['sig']['rsrp'] = 255

            logging.error("Failed fetching signal information")

    def run(self) -> None:
        self._running.set()
        while self._running.is_set():
            try:
                if self._modem:
                    self._update_signal()
            finally:
                pass

            time.sleep(1)

    def get_telemetry(self) -> Dict:
        with self._lock:
            return self.telemetry.copy()

    def stop(self) -> None:
        self._running.clear()
