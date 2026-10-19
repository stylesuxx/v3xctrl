"""Protocol for telemetry data sources."""

from typing import Protocol, TypeVar, runtime_checkable

StateT = TypeVar("StateT", covariant=True)


@runtime_checkable
class TelemetrySource(Protocol[StateT]):
    """Protocol for telemetry data sources.

    All telemetry sources must implement:
    - update() to fetch fresh data
    - get_state() to return the current state

    This protocol uses structural typing - any class implementing these
    methods automatically satisfies this protocol without explicit inheritance.

    The state type is a parameter, so a source and the store method that consumes
    its state are checked against each other where they are registered together.
    """

    def update(self) -> object:
        """Update telemetry data from the source.

        This method should fetch fresh data from the underlying source
        (hardware sensor, system interface, etc.) and update internal state.

        Any return value is ignored by the collector driving this source;
        `GpsTelemetry` reports whether a fresh fix arrived, for the debug apps.

        Raises:
            Exception: Implementation-specific exceptions for hardware/system errors.
        """
        ...

    def get_state(self) -> StateT:
        """Get current telemetry state.

        Returns:
            The source's state dataclass (e.g. BatteryState, ServiceFlags).
        """
        ...
