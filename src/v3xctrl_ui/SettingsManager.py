"""Settings manager for handling configuration updates and hot-reload."""
import copy
import logging
import threading
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from v3xctrl_ui.Settings import Settings
    from v3xctrl_ui.ApplicationModel import ApplicationModel


class SettingsManager:
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
        self.on_menu_clear: Optional[Callable[[], None]] = None

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
        self.model.fullscreen = new_settings.get("video", {}).get("fullscreen", False)
        if fullscreen_previous is not self.model.fullscreen:
            if self.on_display_update:
                self.on_display_update(self.model.fullscreen)

        # Check if network manager needs to be restarted
        if (
            not self.settings_equal(new_settings, "ports") or
            not self.settings_equal(new_settings, "relay")
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

        # Clear menu to force refresh
        if self.on_menu_clear:
            self.on_menu_clear()

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
