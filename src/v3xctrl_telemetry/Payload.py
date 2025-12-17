"""Telemetry payload dataclasses."""
from dataclasses import dataclass


@dataclass
class SignalInfo:
    rsrq: int = -1
    rsrp: int = -1


@dataclass
class CellInfo:
    id: str = '?'
    band: str = '?'


@dataclass
class LocationInfo:
    lat: float = 0.0
    lng: float = 0.0


@dataclass
class BatteryInfo:
    vol: int = 0
    avg: int = 0
    pct: int = 0
    wrn: bool = False


@dataclass
class TelemetryPayload:
    sig: SignalInfo
    cell: CellInfo
    loc: LocationInfo
    bat: BatteryInfo
    svc: int = 0
    vc: int = 0
