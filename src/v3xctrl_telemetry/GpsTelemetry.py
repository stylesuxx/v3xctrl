from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GpsState:
    lat: float = 0.0
    lng: float = 0.0
    fix: bool = False
    fix_type: int = 0  # 0=no fix, 1=dead reckoning, 2=2D, 3=3D, 4=GNSS+DR
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
