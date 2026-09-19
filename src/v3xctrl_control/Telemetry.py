"""
Telemetry coordinator.

Owns a `TelemetryStore` plus one `TelemetryCollector` per data source. Each collector
constructs its source on its own thread and polls it at its own configurable rate, so a
missing or slow device delays neither startup nor the other sources. The send loop reads
the latest snapshot via `get_telemetry()` at whatever rate is appropriate for the
transport.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from v3xctrl_telemetry import GpsProtocol
from v3xctrl_telemetry.BatteryTelemetry import BatteryState, BatteryTelemetry
from v3xctrl_telemetry.dataclasses import (
    GstFlags,
    LocationInfo,
    ModemState,
    ServiceFlags,
    TelemetryRates,
    VideoCoreFlags,
)
from v3xctrl_telemetry.GstTelemetry import GstTelemetry
from v3xctrl_telemetry.ModemTelemetry import ModemTelemetry
from v3xctrl_telemetry.ServiceTelemetry import ServiceTelemetry
from v3xctrl_telemetry.TelemetryCollector import TelemetryCollector
from v3xctrl_telemetry.TelemetrySource import TelemetrySource
from v3xctrl_telemetry.TelemetryStore import TelemetryStore
from v3xctrl_telemetry.UBXGpsTelemetry import UBXGpsTelemetry
from v3xctrl_telemetry.VideoCoreTelemetry import VideoCoreTelemetry

StateT = TypeVar("StateT")


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
        rates: TelemetryRates | None = None,
    ) -> None:
        # gps_protocol is accepted for forward compatibility; today only UBLOX is wired
        del gps_protocol

        rates = rates if rates is not None else TelemetryRates()
        self._store = TelemetryStore()
        self._collectors: list[TelemetryCollector[Any]] = []

        self._register(
            "modem",
            lambda: ModemTelemetry(modem_path),
            ModemState(),
            self._store.update_modem,
            rates.modem,
        )

        self._register(
            "battery",
            lambda: BatteryTelemetry(
                battery_min_voltage,
                battery_max_voltage,
                battery_warn_voltage,
                battery_i2c_address,
                r_shunt_mohms=battery_shunt_mohms,
                max_expected_current_A=battery_max_current,
            ),
            # An absent sensor reports an empty battery
            BatteryState(percentage=0),
            self._store.update_battery,
            rates.battery,
        )

        # The collector polls at the rate the module was programmed to emit at, so each
        # tick drains one fix
        self._register(
            "gps",
            lambda: UBXGpsTelemetry(gps_path, gps_rate_hz),
            LocationInfo(),
            self._store.update_gps,
            float(gps_rate_hz),
        )

        self._register(
            "services",
            ServiceTelemetry,
            ServiceFlags(),
            self._store.update_services,
            rates.services,
        )

        self._register(
            "videocore",
            VideoCoreTelemetry,
            VideoCoreFlags(),
            self._store.update_videocore,
            rates.videocore,
        )

        self._register(
            "gst",
            GstTelemetry,
            GstFlags(),
            self._store.update_gst,
            rates.gst,
        )

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
        name: str,
        factory: Callable[[], TelemetrySource[StateT]],
        unavailable_state: StateT,
        store_updater: Callable[[StateT], None],
        rate_hz: float,
    ) -> None:
        """Give one source a collector.

        The state type binds per call, so a source is checked against the store method
        that consumes its state.
        """
        collector = TelemetryCollector(name, factory, unavailable_state, store_updater, 1.0 / rate_hz)
        self._collectors.append(collector)
