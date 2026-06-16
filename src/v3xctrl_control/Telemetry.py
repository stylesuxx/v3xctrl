"""
Telemetry coordinator.

Owns a `TelemetryStore` plus one `TelemetryCollector` per data source. Each
source is polled at its own configurable rate; the store is kept up to date
in the background. The send loop reads the latest snapshot via
`get_telemetry()` at whatever rate is appropriate for the transport.
"""

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from v3xctrl_telemetry import GpsProtocol
from v3xctrl_telemetry.BatteryTelemetry import BatteryTelemetry
from v3xctrl_telemetry.GpsTelemetry import GpsTelemetry
from v3xctrl_telemetry.GstTelemetry import GstTelemetry
from v3xctrl_telemetry.ModemTelemetry import ModemTelemetry
from v3xctrl_telemetry.ServiceTelemetry import ServiceTelemetry
from v3xctrl_telemetry.TelemetryCollector import TelemetryCollector
from v3xctrl_telemetry.TelemetryStore import TelemetryStore
from v3xctrl_telemetry.UBXGpsTelemetry import UBXGpsTelemetry
from v3xctrl_telemetry.VideoCoreTelemetry import VideoCoreTelemetry

T = TypeVar("T")

logger = logging.getLogger(__name__)


class Telemetry:
    def __init__(
        self,
        modem_path: str,
        battery_min_voltage: int = 3500,
        battery_max_voltage: int = 4200,
        battery_warn_voltage: int = 3700,
        battery_i2c_address: int = 0x40,
        battery_shunt_mohms: int = 100,
        battery_max_current: float = 0.8,
        gps_path: str = "/dev/serial0",
        gps_rate_hz: int = 5,
        gps_protocol: GpsProtocol = GpsProtocol.UBLOX,
        battery_update_rate: float = 10.0,
        gst_update_rate: float = 10.0,
        videocore_update_rate: float = 1.0,
        services_update_rate: float = 0.2,
        modem_update_rate: float = 1.0,
    ) -> None:
        # gps_protocol is accepted for forward compatibility; today only UBLOX is wired
        del gps_protocol

        self._store = TelemetryStore()
        self._collectors: list[TelemetryCollector] = []

        modem = self._init_component("modem", lambda: ModemTelemetry(modem_path))
        self._register(modem, "modem", self._store.update_modem, modem_update_rate)

        battery = self._init_component(
            "battery",
            lambda: BatteryTelemetry(
                battery_min_voltage,
                battery_max_voltage,
                battery_warn_voltage,
                battery_i2c_address,
                r_shunt_mohms=battery_shunt_mohms,
                max_expected_current_A=battery_max_current,
            ),
        )
        self._register(battery, "battery", self._store.update_battery, battery_update_rate)

        gps: GpsTelemetry | None = self._init_component("gps", lambda: UBXGpsTelemetry(gps_path, gps_rate_hz))
        # GPS poll rate intentionally tied to the module's push rate - polling faster
        # blocks on empty serial reads, polling slower drops messages.
        self._register(gps, "gps", self._store.update_gps, float(gps_rate_hz))

        services = self._init_component("services", ServiceTelemetry)
        self._register(services, "services", self._store.update_services, services_update_rate)

        videocore = self._init_component("videocore", VideoCoreTelemetry)
        self._register(videocore, "videocore", self._store.update_videocore, videocore_update_rate)

        gst = self._init_component("gst", GstTelemetry)
        self._register(gst, "gst", self._store.update_gst, gst_update_rate)

    def start(self) -> None:
        for collector in self._collectors:
            collector.start()

    def stop(self) -> None:
        for collector in self._collectors:
            collector.stop()

    def get_telemetry(self) -> dict[str, Any]:
        return self._store.get_snapshot()

    def _register(
        self,
        source: Any | None,
        name: str,
        store_updater: Callable[[Any], None],
        rate_hz: float,
    ) -> None:
        if source is None:
            return

        self._collectors.append(TelemetryCollector(name, source, store_updater, 1.0 / rate_hz))

    @staticmethod
    def _init_component(name: str, factory: Callable[[], T]) -> T | None:
        try:
            return factory()

        except Exception as exc:
            logger.warning("Failed to initialize %s telemetry: %s", name, exc)
            return None
