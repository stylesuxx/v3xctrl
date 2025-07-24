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

from v3xctrl_telemetry import Battery


class Telemetry(threading.Thread):
    def __init__(
        self,
        modem: str = None,
        battery_min_voltage: int = 3500,
        battery_max_voltage: int = 4200,
        battery_warn_voltage: int = 3700,
        battery_i2c_address: int = 0x40,
        interval: float = 1.0
    ):
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
            'bat': {
                'vol': 0,
                'avg': 0,
                'pct': 0,
                'wrn': False
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

        self._battery = Battery(
            battery_min_voltage,
            battery_max_voltage,
            battery_warn_voltage,
            battery_i2c_address
        )

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

    def _update_battery(self) -> None:
        self._battery.update()
        with self._lock:
            self.telemetry['bat']['vol'] = self._battery.voltage
            self.telemetry['bat']['avg'] = self._battery.average_voltage
            self.telemetry['bat']['pct'] = self._battery.percentage
            self.telemetry['bat']['wrn'] = self._battery.warning

    def run(self) -> None:
        self._running.set()
        while self._running.is_set():
            try:
                if self._modem:
                    self._update_signal()
                    self._update_cell()
            except Exception as e:
                logging.error("Telemetry loop error: %s", e)

            self._update_battery()

            time.sleep(self._interval)

    def get_telemetry(self) -> Dict:
        with self._lock:
            return copy.deepcopy(self.telemetry)

    def stop(self) -> None:
        self._running.clear()
