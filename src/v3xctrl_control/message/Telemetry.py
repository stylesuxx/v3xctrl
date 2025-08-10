from typing import Dict, Optional, Any
from .Message import Message


class Telemetry(Message):
    """Message type for telemetry data."""

    def __init__(
        self,
        v: Dict[str, Any] = {},
        timestamp: Optional[float] = None
    ) -> None:
        super().__init__({
            "v": v
        }, timestamp)

        self.values = v

    def get_values(self) -> Dict[str, Any]:
        return self.values
