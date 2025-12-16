import logging
import signal
import threading
import time
from typing import Any, Optional

import pygame

from v3xctrl_ui.ApplicationModel import ApplicationModel
from v3xctrl_ui.EventController import EventController
from v3xctrl_ui.SettingsManager import SettingsManager
from v3xctrl_ui.TimingController import TimingController
from v3xctrl_ui.menu.Menu import Menu
from v3xctrl_ui.OSD import OSD
from v3xctrl_ui.Renderer import Renderer
from v3xctrl_ui.Settings import Settings
from v3xctrl_ui.InputManager import InputManager
from v3xctrl_ui.DisplayManager import DisplayManager
from v3xctrl_ui.NetworkCoordinator import NetworkCoordinator


class AppState:
    """
    Holds the current context of the app.
    """

    @property
    def screen(self) -> pygame.Surface:
        """Get the current screen surface from DisplayManager."""
        return self.display_manager.get_screen()

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.model = ApplicationModel(
          fullscreen=self.settings.get("video", {"fullscreen": False}).get("fullscreen", False),
          throttle=0,
          steering=0
        )

        video = settings.get("video")
        self.size = (video.get("width"), video.get("height"))

        ports = settings.get("ports", {})
        self.video_port = ports.get("video", 6666)
        self.control_port = ports.get("control", 6668)

        self.title = settings.get("settings").get("title")

        self.input_manager = InputManager(settings)

        self.osd = OSD(settings)
        self.renderer = Renderer(self.size, self.settings)

        # Network coordination
        self.network_coordinator = NetworkCoordinator(self.model, self.osd)
        self.network_coordinator.on_connection_change = self._on_connection_change
        self.network_coordinator.create_network_manager(self.settings)

        # Timing
        self.timing_controller = TimingController(self.settings, self.model)

        # Display management
        self.clock = pygame.time.Clock()
        self.display_manager = DisplayManager(self.model, self.size, self.title)

        # Event handling
        self.event_controller = EventController(
            on_quit=self._on_quit,
            on_toggle_fullscreen=self._on_toggle_fullscreen,
            create_menu=self._create_menu,
            on_menu_exit=self.update_settings
        )

        self._setup_signal_handling()

        self.network_coordinator.setup_ports()

        start_time = time.monotonic()
        self.model.last_control_update = start_time
        self.model.last_latency_check = start_time

        # Settings management
        self.settings_manager = SettingsManager(self.settings, self.model)
        self._configure_settings_manager()

    def update_settings(self, new_settings: Optional[Settings] = None) -> None:
        """
        Update settings after exiting menu.
        Only update settings that can be hot reloaded.
        """
        # Clear menu first to ensure clean state
        self.event_controller.clear_menu()

        if new_settings is None:
            new_settings = Settings("settings.toml")
            new_settings.save()

        # Delegate to settings manager
        needs_restart = not self.settings_manager.update_settings(new_settings)

        if needs_restart:
            # Network manager shutdown and recreation handled by restart thread
            self.network_coordinator.shutdown()
            self.network_coordinator.create_network_manager(new_settings)

    def update(self) -> None:
        """Update application state with timed operations."""
        # Check if network restart is complete
        self.settings_manager.check_network_restart_complete()

        now = time.monotonic()
        self.model.loop_history.append(now)

        # Handle control updates, send last values if user is in menu
        if self.timing_controller.should_update_control(now):
            try:
                throttle, steering = (0, 0)
                if not self.event_controller.menu:
                    throttle, steering = self.input_manager.read_inputs()

                self.model.throttle = throttle
                self.model.steering = steering

                self.network_coordinator.send_control_message(throttle, steering)
            except Exception as e:
                logging.warning(f"Input read error: {e}")
            self.timing_controller.mark_control_updated(now)

        # Handle latency checks
        if self.timing_controller.should_check_latency(now):
            self.network_coordinator.send_latency_check()
            self.timing_controller.mark_latency_checked(now)

    def tick(self) -> None:
        self.clock.tick(self.timing_controller.main_loop_fps)

    def handle_events(self) -> bool:
        """
        Handle pygame events. Returns False if application should quit.
        """
        return self.event_controller.handle_events()

    def render(self) -> None:
        """Render the current frame."""
        # Update OSD with network data
        data_left = self.network_coordinator.get_data_queue_size()
        if self.network_coordinator.has_server_error():
            self.osd.update_debug_status("fail")

        buffer_size = self.network_coordinator.get_video_buffer_size()
        self.osd.update_buffer_queue(buffer_size)

        self.osd.update_data_queue(data_left)
        self.osd.set_control(self.model.throttle, self.model.steering)

        self.renderer.render_all(
            self,
            self.network_coordinator.network_manager,
            self.model.fullscreen,
            self.model.scale
        )

    def shutdown(self) -> None:
        logging.info("Shutting down...")

        # Wait for any pending network restart
        self.settings_manager.wait_for_network_restart()

        pygame.quit()

        start = time.monotonic()
        self.input_manager.shutdown()
        delta = round(time.monotonic() - start)
        logging.debug(f"Input manager shut down after {delta}s")

        self.network_coordinator.shutdown()

        delta = round(time.monotonic() - start)
        logging.info(f"Shutdown took {delta}s")

    def _on_quit(self) -> None:
        """Callback for quit event."""
        self.model.running = False

    def _on_toggle_fullscreen(self) -> None:
        """Callback for fullscreen toggle."""
        self.display_manager.toggle_fullscreen()

    def _create_menu(self) -> Menu:
        """Callback to create a new menu instance."""
        menu = Menu(
            self.screen.get_size()[0],
            self.screen.get_size()[1],
            self.input_manager.gamepad_manager,
            self.settings,
            self.network_coordinator.send_command,
            self.update_settings,
            self._signal_handler
        )
        menu.set_tab_enabled("Streamer", self.network_coordinator.is_control_connected())
        return menu

    def _configure_settings_manager(self) -> None:
        """Configure settings manager with all necessary callbacks."""
        def update_timing(settings: Settings) -> None:
            self.timing_controller.settings = settings
            self.timing_controller.update_from_settings()
            self.settings = settings

        def update_network(settings: Settings) -> None:
            self._update_network_settings()

        def update_input(settings: Settings) -> None:
            self.input_manager.update_settings(settings)

        def update_osd(settings: Settings) -> None:
            self.osd.update_settings(settings)

        def update_renderer(settings: Settings) -> None:
            self.renderer.settings = settings

        def update_display(fullscreen: bool) -> None:
            self.display_manager.set_fullscreen(fullscreen)

        def create_restart_thread(new_settings: Settings) -> threading.Thread:
            return self.network_coordinator.restart_network_manager(new_settings)

        self.settings_manager.on_timing_update = update_timing
        self.settings_manager.on_network_update = update_network
        self.settings_manager.on_input_update = update_input
        self.settings_manager.on_osd_update = update_osd
        self.settings_manager.on_renderer_update = update_renderer
        self.settings_manager.on_display_update = update_display
        self.settings_manager.create_network_restart_thread = create_restart_thread
        self.settings_manager.network_restart_complete = self.network_coordinator.restart_complete

    def _update_network_settings(self) -> None:
        udp_ttl_ms = self.settings.get("udp_packet_ttl", 100)
        self.network_coordinator.update_ttl(udp_ttl_ms)

    def _on_connection_change(self, connected: bool) -> None:
        """Callback for connection state changes."""
        self.event_controller.set_menu_tab_enabled("Streamer", connected)

    def _setup_signal_handling(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(
        self,
        sig: Optional[int] = None,
        frame: Optional[Any] = None
    ) -> None:
        """Handle shutdown signals gracefully."""
        self.event_controller.clear_menu()
        if self.model.running:
            self.model.running = False
