"""
Thread-safe store for the current telemetry payload.

Each source writes its own slice via the matching `update_*` method; the send
loop reads a full snapshot via `get_snapshot()`. The lock is held only for
nanosecond-scale field copies - no I/O ever happens under the lock, so writers
never block on a reader and vice versa.
"""

import threading
from dataclasses import asdict
from typing import Any

from v3xctrl_telemetry.BatteryTelemetry import BatteryState
from v3xctrl_telemetry.dataclasses import (
    BatteryInfo,
    CellInfo,
    GstFlags,
    LocationInfo,
    ModemState,
    ServiceFlags,
    SignalInfo,
    TelemetryPayload,
    VideoCoreFlags,
)


class TelemetryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload = TelemetryPayload(
            sig=SignalInfo(),
            cell=CellInfo(),
            loc=LocationInfo(),
            bat=BatteryInfo(),
            svc=0,
            vc=0,
            gst=0,
        )

    def update_modem(self, state: ModemState) -> None:
        with self._lock:
            self._payload.sig.rsrq = state.rsrq
            self._payload.sig.rsrp = state.rsrp
            self._payload.cell.id = state.cell_id
            self._payload.cell.band = state.band

    def update_battery(self, state: BatteryState) -> None:
        with self._lock:
            self._payload.bat.vol = state.voltage
            self._payload.bat.avg = state.average_voltage
            self._payload.bat.pct = state.percentage
            self._payload.bat.wrn = state.warning
            self._payload.bat.cur = state.current

    def update_gps(self, state: LocationInfo) -> None:
        with self._lock:
            self._payload.loc = state

    def update_services(self, flags: ServiceFlags) -> None:
        with self._lock:
            self._payload.svc = int(flags)

    def update_videocore(self, flags: VideoCoreFlags) -> None:
        with self._lock:
            self._payload.vc = int(flags)

    def update_gst(self, flags: GstFlags) -> None:
        with self._lock:
            self._payload.gst = int(flags)

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._payload)
