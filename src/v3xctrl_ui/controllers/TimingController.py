"""Timing controller for managing frame rates and update intervals."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from v3xctrl_ui.utils.Settings import Settings
    from v3xctrl_ui.core.ApplicationModel import ApplicationModel


class TimingController:
    """Manages timing intervals and frame rate limits."""

    def __init__(self, settings: 'Settings', model: 'ApplicationModel'):
        """Initialize timing controller with settings.

        Args:
            settings: Application settings containing timing configuration
            model: Application model to update with timing intervals
        """
        self.settings = settings
        self.model = model
        self.main_loop_fps: int = 60
        self.update_from_settings()

    def update_from_settings(self) -> None:
        """Update timing intervals from current settings."""
        timing = self.settings.get("timing", {})
        control_rate_frequency = timing.get("control_update_hz", 30)
        latency_check_frequency = timing.get("latency_check_hz", 1)

        self.model.control_interval = 1.0 / control_rate_frequency
        self.model.latency_interval = 1.0 / latency_check_frequency
        self.main_loop_fps = timing.get("main_loop_fps", 60)

    def should_update_control(self, now: float) -> bool:
        """Check if enough time has passed for a control update.

        Args:
            now: Current monotonic time

        Returns:
            True if a control update should occur
        """
        return now - self.model.last_control_update >= self.model.control_interval

    def should_check_latency(self, now: float) -> bool:
        """Check if enough time has passed for a latency check.

        Args:
            now: Current monotonic time

        Returns:
            True if a latency check should occur
        """
        return now - self.model.last_latency_check >= self.model.latency_interval

    def mark_control_updated(self, now: float) -> None:
        """Mark that a control update has occurred.

        Args:
            now: Current monotonic time
        """
        self.model.last_control_update = now

    def mark_latency_checked(self, now: float) -> None:
        """Mark that a latency check has occurred.

        Args:
            now: Current monotonic time
        """
        self.model.last_latency_check = now
