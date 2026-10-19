"""Timing controller for managing frame rates and update intervals."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from v3xctrl_ui.core.dataclasses import ApplicationModel
    from v3xctrl_ui.core.Settings import Settings


class TimingController:
    """Manages timing intervals and frame rate limits."""

    # Epsilon for floating-point comparison tolerance
    TIMING_EPSILON = 1e-9

    def __init__(self, settings: "Settings", model: "ApplicationModel"):
        """Initialize timing controller with settings.

        Args:
            settings: Application settings containing timing configuration
            model: Application model to update with timing intervals
        """
        self.settings = settings
        self.model = model
        self.update_from_settings()

    def apply_settings(self, settings: "Settings") -> None:
        self.settings = settings
        self.update_from_settings()

    def update_from_settings(self) -> None:
        """Update timing intervals from current settings."""
        timing = self.settings.timing

        self.model.control_interval = 1.0 / timing.control_update_hz
        self.model.latency_interval = 1.0 / timing.latency_check_hz
        self.main_loop_fps = timing.main_loop_fps

    def should_check_latency(self, now: float) -> bool:
        """Check if enough time has passed for a latency check.

        Args:
            now: Current monotonic time

        Returns:
            True if a latency check should occur
        """
        return now - self.model.last_latency_check >= self.model.latency_interval - self.TIMING_EPSILON

    def mark_latency_checked(self, now: float) -> None:
        """Mark that a latency check has occurred.

        Args:
            now: Current monotonic time
        """
        self.model.last_latency_check = now
