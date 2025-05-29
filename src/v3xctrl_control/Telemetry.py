"""
This class collects telemetry data, all fetching of telemetry data should happen
here.

The only public interface is the get_telemetry() method.
"""
from atlib import AIR780EU
import copy
import logging
from typing import Dict
import threading
import time


class Telemetry(threading.Thread):
    def __init__(self, modem: str = None, interval: float = 1.0):
        super().__init__(daemon=True)

        self._interval = interval
        self.telemetry = {
            'sig': {
                'rsrq': -1,
                'rsrp': -1
            },
            'cell': {
                'id': 0,
                'band': 0,
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
        self._modem = None
        try:
            self._modem = AIR780EU(modem)
            if not self._modem:
                logging.warning("Modem unavailable; telemetry will contain placeholders.")
        except Exception as e:
            logging.error("Failed to initialize modem: %s", e)

    def _set_signal_unknown(self):
        with self._lock:
            self.telemetry['sig']['rsrq'] = -1
            self.telemetry['sig']['rsrp'] = -1

    def _set_cell_unknown(self):
        with self._lock:
            self.telemetry['cell']['band'] = 0

    def _update_signal(self) -> None:
        try:
            signal_quality = self._modem.get_signal_quality()
            with self._lock:
                self.telemetry['sig']['rsrq'] = signal_quality.rsrq
                self.telemetry['sig']['rsrp'] = signal_quality.rsrp
        except Exception as e:
            self._set_signal_unknown()

            logging.error("Failed fetching signal information: %s", e)

    def _update_cell(self) -> None:
        try:
            band = self._modem.get_active_band()
            with self._lock:
                self.telemetry['cell']['band'] = band
        except Exception as e:
            self._set_cell_unknown()

            logging.error("Failed fetching cell information: %s", e)

    def run(self) -> None:
        self._running.set()
        while self._running.is_set():
            try:
                if self._modem:
                    self._update_signal()
                    self._update_cell()
            except Exception as e:
                logging.error("Telemetry loop error: %s", e)

            time.sleep(self._interval)

    def get_telemetry(self) -> Dict:
        with self._lock:
            return copy.deepcopy(self.telemetry)

    def stop(self) -> None:
        self._running.clear()
