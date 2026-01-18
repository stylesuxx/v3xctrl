"""Settings manager for handling configuration updates and hot-reload."""
import copy
import logging
import threading
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from v3xctrl_ui.utils.Settings import Settings
    from v3xctrl_ui.core.ApplicationModel import ApplicationModel


class SettingsController:
    """Manages settings updates, comparison, and component coordination."""

    def __init__(
        self,
        settings: 'Settings',
        model: 'ApplicationModel'
    ):
        """Initialize settings manager.

        Args:
            settings: Initial application settings
            model: Application model to store pending settings
        """
        self.settings = settings
        self.model = model
        self.old_settings = copy.deepcopy(settings)

        # Network restart coordination
        self.network_restart_thread: Optional[threading.Thread] = None
        self.network_restart_complete = threading.Event()

        # Callbacks for component updates
        self.on_timing_update: Optional[Callable[['Settings'], None]] = None
        self.on_network_update: Optional[Callable[['Settings'], None]] = None
        self.on_input_update: Optional[Callable[['Settings'], None]] = None
        self.on_osd_update: Optional[Callable[['Settings'], None]] = None
        self.on_renderer_update: Optional[Callable[['Settings'], None]] = None
        self.on_display_update: Optional[Callable[[bool], None]] = None

        # Callback for network restart
        self.create_network_restart_thread: Optional[Callable[['Settings'], threading.Thread]] = None

    def update_settings(self, new_settings: 'Settings') -> bool:
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
            if self.on_display_update:
                self.on_display_update(fullscreen_new)

        # Check if network manager needs to be restarted
        if (
            not self.settings_equal(new_settings, "ports") or
            self._needs_relay_restart(new_settings)
        ):
            logging.info("Restarting network manager")
            self.model.pending_settings = new_settings

            if self.create_network_restart_thread:
                self.network_restart_thread = self.create_network_restart_thread(new_settings)
                self.network_restart_thread.start()

            return False

        # Apply settings immediately if no network restart needed
        self.apply_settings(new_settings)
        return True

    def check_network_restart_complete(self) -> bool:
        """Check if network restart is complete and apply pending settings.

        Returns:
            True if restart was complete and settings were applied
        """
        if self.network_restart_complete.is_set():
            self.network_restart_complete.clear()

            if self.model.pending_settings:
                self.apply_settings(self.model.pending_settings)
                self.model.pending_settings = None

            logging.info("Network manager restart complete")
            return True

        return False

    def apply_settings(self, new_settings: 'Settings') -> None:
        """Apply new settings to all components.

        Args:
            new_settings: Settings to apply
        """
        # Update settings and old_settings
        self.settings = new_settings
        self.old_settings = copy.deepcopy(new_settings)

        # Update all components via callbacks
        if self.on_timing_update:
            self.on_timing_update(new_settings)

        if self.on_network_update:
            self.on_network_update(new_settings)

        if self.on_input_update:
            self.on_input_update(new_settings)

        if self.on_osd_update:
            self.on_osd_update(new_settings)

        if self.on_renderer_update:
            self.on_renderer_update(new_settings)

    def _needs_relay_restart(self, new_settings: 'Settings') -> bool:
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
        if new_enabled and (
            old_id != new_id or
            old_server != new_server or
            old_spectator != new_spectator
        ):
            return True

        # Direct mode: spectator enabled (requires session ID for relay connection)
        if not new_enabled and not old_spectator and new_spectator and has_session_id:
            return True

        return False

    def settings_equal(self, new_settings: 'Settings', key: str) -> bool:
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

        for section_key in old_section:
            if new_section.get(section_key) != old_section.get(section_key):
                return False

        return True

    def wait_for_network_restart(self, timeout: float = 5.0) -> bool:
        """Wait for pending network restart to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if restart completed within timeout
        """
        if self.network_restart_thread and self.network_restart_thread.is_alive():
            logging.info("Waiting for network restart to complete...")
            self.network_restart_thread.join(timeout=timeout)
            return not self.network_restart_thread.is_alive()

        return True
