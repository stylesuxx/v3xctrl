"""Settings manager for handling configuration updates and hot-reload."""

import copy
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from v3xctrl_ui.core.SettingsSubscriber import NetworkRestarter, SettingsSubscriber

if TYPE_CHECKING:
    from v3xctrl_ui.core.dataclasses import ApplicationModel
    from v3xctrl_ui.core.Settings import Settings

logger = logging.getLogger(__name__)


class SettingsController:
    """Manages settings updates, comparison, and component coordination."""

    def __init__(
        self,
        settings: "Settings",
        model: "ApplicationModel",
        network_restarter: NetworkRestarter,
        on_fullscreen_change: Callable[[bool], None],
    ):
        """Initialize settings manager.

        Args:
            settings: Initial application settings
            model: Application model to store pending settings
            network_restarter: The network stack, restarted when ports, relay or
                transport change
            on_fullscreen_change: Called with the new fullscreen state as soon as
                it changes, ahead of any network restart, so the window responds
                to the save immediately
        """
        self.settings = settings
        self.model = model
        self.old_settings = copy.deepcopy(settings)
        self.network_restarter = network_restarter
        self.on_fullscreen_change = on_fullscreen_change

        self._subscribers: list[SettingsSubscriber] = []

    def register(self, subscriber: SettingsSubscriber) -> None:
        """Add a subscriber. Subscribers are notified in registration order."""
        self._subscribers.append(subscriber)

    def update_settings(self, new_settings: "Settings") -> bool:
        """Update settings and coordinate component updates.

        Args:
            new_settings: New settings to apply

        Returns:
            True if settings were applied immediately, False if network restart needed
        """
        # Handle fullscreen changes
        fullscreen_previous = self.model.fullscreen
        fullscreen_new = new_settings.get("video", {}).get("fullscreen", False)
        if fullscreen_previous != fullscreen_new:
            self.on_fullscreen_change(fullscreen_new)

        # Skip network restart if user hasn't connected yet
        if not self.model.user_connected:
            self.apply_settings(new_settings)
            return True

        # Check if network manager needs to be restarted
        if (
            not self.settings_equal(new_settings, "ports")
            or self._needs_relay_restart(new_settings)
            or self._transport_changed(new_settings)
        ):
            self.model.pending_settings = new_settings
            self.network_restarter.restart(new_settings)

            return False

        # Apply settings immediately if no network restart needed
        self.apply_settings(new_settings)
        return True

    def check_network_restart_complete(self) -> bool:
        """Check if network restart is complete and apply pending settings.

        Returns:
            True if restart was complete and settings were applied
        """
        if self.network_restarter.is_restart_complete():
            self.network_restarter.acknowledge_restart()

            if self.model.pending_settings:
                self.apply_settings(self.model.pending_settings)
                self.model.pending_settings = None

            return True

        return False

    def apply_settings(self, new_settings: "Settings") -> None:
        """Hand the new settings to every subscriber.

        Args:
            new_settings: Settings to apply
        """
        self.settings = new_settings
        self.old_settings = copy.deepcopy(new_settings)

        for subscriber in self._subscribers:
            subscriber.apply_settings(new_settings)

    def _needs_relay_restart(self, new_settings: "Settings") -> bool:
        """Check if relay settings changes require a network restart.

        Restart is needed when:
        - Relay enabled/disabled toggled (with session ID present)
        - Relay enabled and session ID, server, or spectator mode changed
        - Direct mode and spectator mode enabled (with session ID present)

        Args:
            new_settings: New settings to compare

        Returns:
            True if network restart is needed
        """
        old_relay = self.old_settings.get("relay", {})
        new_relay = new_settings.get("relay", {})

        old_enabled = old_relay.get("enabled", False)
        new_enabled = new_relay.get("enabled", False)

        old_spectator = old_relay.get("spectator_mode", False)
        new_spectator = new_relay.get("spectator_mode", False)

        old_id = old_relay.get("id", "")
        new_id = new_relay.get("id", "")

        old_server = old_relay.get("server", "")
        new_server = new_relay.get("server", "")

        has_session_id = bool(new_id)

        # Relay toggled on/off (requires session ID)
        if old_enabled != new_enabled and has_session_id:
            return True

        # Relay enabled: check if connection settings changed
        if new_enabled and (old_id != new_id or old_server != new_server or old_spectator != new_spectator):
            return True

        # Direct mode: spectator enabled (requires session ID for relay connection)
        if not new_enabled and not old_spectator and new_spectator and has_session_id:  # noqa: SIM103
            return True

        return False

    def _transport_changed(self, new_settings: "Settings") -> bool:
        """Check if transport setting changed (udp <-> tcp)."""
        old_transport = self.old_settings.get("transport", "udp")
        new_transport = new_settings.get("transport", "udp")
        return old_transport != new_transport

    def settings_equal(self, new_settings: "Settings", key: str) -> bool:
        """Compare a section of settings with the old settings.

        Args:
            new_settings: New settings to compare
            key: Section key to compare

        Returns:
            True if the sections are equal
        """
        old_section = self.old_settings.get(key)
        new_section = new_settings.get(key)

        # If both are None or missing, consider them equal
        if old_section is None and new_section is None:
            return True

        # If one is None and the other isn't, they're different
        if old_section is None or new_section is None:
            return False

        if new_section.keys() != old_section.keys():
            return False

        return all(new_section.get(section_key) == old_section.get(section_key) for section_key in old_section)

    def wait_for_network_restart(self, timeout: float = 5.0) -> bool:
        """Wait for pending network restart to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if restart completed within timeout
        """
        return self.network_restarter.wait_for_restart(timeout)
