"""Protocol for telemetry data sources."""
from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class TelemetrySource(Protocol):
    """Protocol for telemetry data sources.

    All telemetry sources must implement:
    - update() to fetch fresh data
    - get_state() to return current state as a dataclass or dict

    This protocol uses structural typing - any class implementing these
    methods automatically satisfies this protocol without explicit inheritance.
    """

    def update(self) -> None:
        """Update telemetry data from the source.

        This method should fetch fresh data from the underlying source
        (hardware sensor, system interface, etc.) and update internal state.

        Raises:
            Exception: Implementation-specific exceptions for hardware/system errors.
        """
        ...

    def get_state(self) -> Any:
        """Get current telemetry state.

        Returns:
            Any: Current state as a dataclass or dict. The specific return type
                 depends on the telemetry source (e.g., BatteryState, Services, etc.).
        """
        ...
