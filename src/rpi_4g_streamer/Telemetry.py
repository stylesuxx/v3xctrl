"""
This class collects telemetry data, all fetching of telemetry data should happen
here.

The only public interface is the get_telemetry() method.
"""
from atlib import AIR780EU
from enum import IntEnum
from typing import Dict
import threading
import time


class SignalQuality(IntEnum):
    POOR = 0
    FAIR = 1
    GOOD = 2
    EXCELLENT = 3


class Telemetry(threading.Thread):
    def __init__(self, modem: str = None):
        super().__init__(daemon=True)

        self.telemetry = {
            'loc': {
                'lat': 0,
                'lng': 0,
            },
            'sig': {
                'bar': 0,
                'qty': int(SignalQuality.POOR),
            },
            'ina': {
                'vol': 0,
                'cur': 0
            }
        }

        self._running = threading.Event()
        self._modem = AIR780EU(modem) if modem else None
        self._lock = threading.Lock()

    def _update_signal(self) -> None:
        def rsrp_to_dbm(value: int) -> int:
            if value == 255:
                return -140  # Unknown
            return value - 140

        def rsrq_to_dbm(value: int) -> float:
            if value == 255:
                return -20.0  # Unknown
            return (value * 0.5) - 19.5

        def get_bars(rsrp_dbm: int) -> int:
            """Returns the number of bars based on the RSRP value."""
            if rsrp_dbm >= -80:
                return 5
            elif rsrp_dbm >= -90:
                return 4
            elif rsrp_dbm >= -100:
                return 3
            elif rsrp_dbm >= -110:
                return 2
            else:
                return 1

        def classify_rsrq(rsrq_dbm: float) -> SignalQuality:
            """Classify RSRQ (in dB) into quality tiers."""
            if rsrq_dbm >= -10:
                return SignalQuality.EXCELLENT
            elif rsrq_dbm >= -15:
                return SignalQuality.GOOD
            elif rsrq_dbm >= -20:
                return SignalQuality.FAIR
            else:
                return SignalQuality.POOR

        signal_quality = self._modem.get_signal_quality()
        rsrq_dbm = rsrq_to_dbm(signal_quality.rsrq)
        rsrp_dbm = rsrp_to_dbm(signal_quality.rsrp)

        bars = get_bars(rsrp_dbm)
        quality = classify_rsrq(rsrq_dbm)

        with self._lock:
            self.telemetry['sig']['bar'] = bars
            self.telemetry['sig']['qty'] = int(quality)

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
