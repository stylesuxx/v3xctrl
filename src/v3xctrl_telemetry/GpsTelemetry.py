from abc import ABC, abstractmethod

from v3xctrl_telemetry.dataclasses import GpsFix, LocationInfo


class GpsTelemetry(ABC):
    def __init__(self) -> None:
        self._state = LocationInfo()

    @abstractmethod
    def update(self) -> bool:
        """Read pending data. Returns True if state was updated."""
        ...

    def get_state(self) -> LocationInfo:
        return self._state

    def get_fix(self) -> GpsFix | None:
        """Override where the protocol carries a full fix. NMEA and modem sources do not."""
        return None
