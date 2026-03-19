from abc import ABC, abstractmethod
from dataclasses import dataclass

from v3xctrl_telemetry.dataclasses import GpsFixType


@dataclass
class GpsState:
    lat: float = 0.0
    lng: float = 0.0
    fix_type: GpsFixType = GpsFixType.NO_FIX
    speed: float = 0.0  # km/h
    sats: int = 0


class GpsTelemetry(ABC):
    def __init__(self) -> None:
        self._state = GpsState()

    @abstractmethod
    def update(self) -> bool:
        """Read pending data. Returns True if state was updated."""
        ...

    def get_state(self) -> GpsState:
        return self._state
