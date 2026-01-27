"""
This class collects telemetry data, all fetching of telemetry data should happen
here.

The only public interface is the get_telemetry() method.
"""
from atlib import AIR780EU
from dataclasses import asdict
import logging
from typing import Callable, Dict, Optional, Any, TypeVar
import threading
import time

from v3xctrl_telemetry import (
    SignalInfo,
    CellInfo,
    LocationInfo,
    BatteryInfo,
    TelemetryPayload
)
from v3xctrl_telemetry.BatteryTelemetry import BatteryTelemetry
from v3xctrl_telemetry.ServiceTelemetry import ServiceTelemetry
from v3xctrl_telemetry.VideoCoreTelemetry import VideoCoreTelemetry
from v3xctrl_telemetry.GstTelemetry import GstTelemetry

T = TypeVar("T")


class Telemetry(threading.Thread):
    _SIM_RECHECK_INTERVAL = 30

    def __init__(
        self,
        modem_path: str,
        battery_min_voltage: int = 3500,
        battery_max_voltage: int = 4200,
        battery_warn_voltage: int = 3700,
        battery_i2c_address: int = 0x40,
        battery_shunt_mohms: int = 100,
        battery_max_current: float = 0.8,
        interval: float = 1.0
    ) -> None:
        super().__init__(daemon=True)

        self._modem_path = modem_path
        self._interval = interval
        self.payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=LocationInfo(),
            bat=BatteryInfo(),
            svc=0,
            vc=0,
            gst=0
        )

        self._running = threading.Event()
        self._lock = threading.Lock()

        self._modem: Optional[AIR780EU] = None
        self._sim_absent = False
        self._sim_recheck_counter = 0
        self._init_modem()

        self._battery = self._init_component(
            "Battery",
            lambda: BatteryTelemetry(
                battery_min_voltage,
                battery_max_voltage,
                battery_warn_voltage,
                battery_i2c_address,
                r_shunt_mohms=battery_shunt_mohms,
                max_expected_current_A=battery_max_current
            )
        )
        self._services = self._init_component("service", ServiceTelemetry)
        self._videocore = self._init_component("VideoCore", VideoCoreTelemetry)
        self._gst = self._init_component("GST", GstTelemetry)

    def get_telemetry(self) -> Dict[str, Any]:
        with self._lock:
            return asdict(self.payload)

    def run(self) -> None:
        self._running.set()
        while self._running.is_set():
            if self._modem_available():
                self._update_signal()
                self._update_cell()

            self._update_battery()
            self._update_services()
            self._update_videocore()
            self._update_gst()

            time.sleep(self._interval)

    def stop(self) -> None:
        self._running.clear()

    def _init_component(self, name: str, factory: Callable[[], T]) -> Optional[T]:
        try:
            return factory()

        except Exception as e:
            logging.warning("Failed to initialize %s telemetry: %s", name, e)
            return None

    def _modem_available(self) -> bool:
        if self._modem:
            return True

        if self._sim_absent:
            self._sim_recheck_counter += 1
            if self._sim_recheck_counter < self._SIM_RECHECK_INTERVAL:
                return False
            self._sim_recheck_counter = 0

        return self._init_modem()

    def _init_modem(self) -> bool:
        try:
            self._modem = AIR780EU(self._modem_path)
            self._modem.enable_location_reporting()
            if not self._modem:
                logging.warning("Modem unavailable")
                self._modem = None
                return False

            sim_status = self._modem.get_sim_status()
            if sim_status != "OK":
                logging.info("No SIM card present (status: %s)", sim_status)
                self._modem = None
                self._sim_absent = True
                return False

            self._sim_absent = False
            logging.info("Modem initialized")
            return True

        except Exception as e:
            logging.warning("Failed to initialize modem: %s", e)
            self._modem = None
            return False

    def _set_signal_unknown(self) -> None:
        with self._lock:
            self.payload.sig.rsrq = -1
            self.payload.sig.rsrp = -1

    def _set_cell_unknown(self) -> None:
        with self._lock:
            self.payload.cell.id = "?"
            self.payload.cell.band = "?"

    def _update_signal(self) -> None:
        try:
            signal_quality = self._modem.get_signal_quality()
            with self._lock:
                self.payload.sig.rsrq = signal_quality.rsrq
                self.payload.sig.rsrp = signal_quality.rsrp
        except Exception as e:
            self._set_signal_unknown()
            logging.debug("Failed to fetch signal information: %s", e)
            self._modem = None

    def _update_cell(self) -> None:
        try:
            band = self._modem.get_active_band()
            id = self._modem.get_cell_location()[3]
            with self._lock:
                self.payload.cell.id = id
                self.payload.cell.band = band
        except Exception as e:
            self._set_cell_unknown()
            logging.debug("Failed to fetch cell information: %s", e)
            self._modem = None

    def _update_battery(self) -> None:
        if self._battery:
            self._battery.update()
            state = self._battery.get_state()
            with self._lock:
                self.payload.bat.vol = state.voltage
                self.payload.bat.avg = state.average_voltage
                self.payload.bat.pct = state.percentage
                self.payload.bat.wrn = state.warning
                self.payload.bat.cur = state.current

    def _update_services(self) -> None:
        if self._services:
            try:
                self._services.update()
                with self._lock:
                    self.payload.svc = self._services.get_byte()
            except Exception as e:
                logging.debug("Failed to update service telemetry: %s", e)
                with self._lock:
                    self.payload.svc = 0

    def _update_videocore(self) -> None:
        if self._videocore:
            try:
                self._videocore.update()
                with self._lock:
                    self.payload.vc = self._videocore.get_byte()
            except Exception as e:
                logging.debug("Failed to update VideoCore telemetry: %s", e)
                with self._lock:
                    self.payload.vc = 0

    def _update_gst(self) -> None:
        if self._gst:
            try:
                self._gst.update()
                with self._lock:
                    self.payload.gst = self._gst.get_byte()
            except Exception as e:
                logging.debug("Failed to update GST telemetry: %s", e)
                with self._lock:
                    self.payload.gst = 0
