from typing import Any
from .Message import Message


class Control(Message):
    """Message type for telemetry data."""

    def __init__(self, v: dict[str, Any] = {}, timestamp: float | None = None) -> None:
        super().__init__({
            "v": v
        }, timestamp)

        self.values = v

    def get_values(self) -> dict[str, Any]:
        return self.values
