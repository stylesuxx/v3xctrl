from abc import ABC, abstractmethod

from v3xctrl_telemetry.dataclasses import LocationInfo


class GpsTelemetry(ABC):
    def __init__(self) -> None:
        self._state = LocationInfo()

    @abstractmethod
    def update(self) -> bool:
        """Read pending data. Returns True if state was updated."""
        ...

    def get_state(self) -> LocationInfo:
        return self._state
