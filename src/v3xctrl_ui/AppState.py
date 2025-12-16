import logging
import signal
import threading
import time
from typing import Any, Callable, Dict, Optional

import pygame

from v3xctrl_control import State
from v3xctrl_control.message import Command
from v3xctrl_control.message import Control, Latency, Telemetry

from v3xctrl_ui.ApplicationModel import ApplicationModel
from v3xctrl_ui.EventController import EventController
from v3xctrl_ui.SettingsManager import SettingsManager
from v3xctrl_ui.TimingController import TimingController
from v3xctrl_ui.Init import Init
from v3xctrl_ui.menu.Menu import Menu
from v3xctrl_ui.OSD import OSD
from v3xctrl_ui.Renderer import Renderer
from v3xctrl_ui.Settings import Settings
from v3xctrl_ui.NetworkManager import NetworkManager
from v3xctrl_ui.InputManager import InputManager


class AppState:
    """
    Holds the current context of the app.
    """
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

        self.handlers = self._create_handlers()
        self.network_manager = NetworkManager(
            self.settings,
            self.handlers
        )

        # Timing
        self.timing_controller = TimingController(self.settings, self.model)

        self.screen, self.clock = Init.ui(self.size, self.title)
        if self.model.fullscreen:
            self._update_screen_size()

        # Event handling
        self.event_controller = EventController(
            on_quit=self._on_quit,
            on_toggle_fullscreen=self._on_toggle_fullscreen,
            create_menu=self._create_menu,
            on_menu_exit=self.update_settings
        )

        self._setup_signal_handling()

        self.network_manager.setup_ports()

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
        if new_settings is None:
            new_settings = Init.settings("settings.toml")

        # Delegate to settings manager
        needs_restart = not self.settings_manager.update_settings(new_settings)

        if needs_restart:
            # Network manager shutdown and recreation handled by restart thread
            self.network_manager.shutdown()
            self.network_manager = NetworkManager(
                new_settings,
                self.handlers
            )

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

                self._send_control_message()
            except Exception as e:
                logging.warning(f"Input read error: {e}")
            self.timing_controller.mark_control_updated(now)

        # Handle latency checks
        if self.timing_controller.should_check_latency(now):
            self.network_manager.send_latency_check()
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
        data_left = self.network_manager.get_data_queue_size()
        if self.network_manager.server_error:
            self.osd.update_debug_status("fail")

        if self.network_manager.video_receiver:
            buffer_size = len(self.network_manager.video_receiver.frame_buffer)
            self.osd.update_buffer_queue(buffer_size)

        self.osd.update_data_queue(data_left)
        self.osd.set_control(self.model.throttle, self.model.steering)

        self.renderer.render_all(
            self,
            self.network_manager,
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

        start_nm = time.monotonic()
        self.network_manager.shutdown()
        delta = round(time.monotonic() - start_nm)
        logging.debug(f"Network manager shut down after {delta}s")

        delta = round(time.monotonic() - start)
        logging.info(f"Shutdown took {delta}s")

    def _restart_network_manager(self, new_settings: Settings) -> None:
        """
        Background thread function to restart network manager.
        This runs in a separate thread to avoid blocking the UI.
        """
        try:
            logging.debug("Shutting down old network manager...")
            self.network_manager.shutdown()

            logging.debug("Creating new network manager...")
            self.network_manager = NetworkManager(
                new_settings,
                self.handlers
            )

            self.network_manager.setup_ports()

        except Exception as e:
            logging.error(f"Network manager restart failed: {e}")

        finally:
            self.settings_manager.network_restart_complete.set()

    def _on_quit(self) -> None:
        """Callback for quit event."""
        self.model.running = False

    def _on_toggle_fullscreen(self) -> None:
        """Callback for fullscreen toggle."""
        self.model.fullscreen = not self.model.fullscreen
        self._update_screen_size()

    def _create_menu(self) -> Menu:
        """Callback to create a new menu instance."""
        def invoke_command(
            command: Command,
            callback: Callable[[bool], None]
        ) -> None:
            if self.network_manager.server:
                self.network_manager.server.send_command(command, callback)
            else:
                logging.error(f"Server is not set, cannot send command: {command}")

        menu = Menu(
            self.screen.get_size()[0],
            self.screen.get_size()[1],
            self.input_manager.gamepad_manager,
            self.settings,
            invoke_command,
            self.update_settings,
            self._signal_handler
        )
        menu.set_tab_enabled("Streamer", self.model.control_connected)
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
            self._update_screen_size()

        def clear_menu() -> None:
            self.event_controller.clear_menu()

        def create_restart_thread(new_settings: Settings) -> threading.Thread:
            return threading.Thread(
                target=self._restart_network_manager,
                args=(new_settings,)
            )

        self.settings_manager.on_timing_update = update_timing
        self.settings_manager.on_network_update = update_network
        self.settings_manager.on_input_update = update_input
        self.settings_manager.on_osd_update = update_osd
        self.settings_manager.on_renderer_update = update_renderer
        self.settings_manager.on_display_update = update_display
        self.settings_manager.on_menu_clear = clear_menu
        self.settings_manager.create_network_restart_thread = create_restart_thread

    def _update_screen_size(self) -> None:
        if self.model.fullscreen:
            # SCALED is important here, this makes it a resizable, borderless
            # window instead of "just" the legacy FULLSCREEN mode which causes
            # a bunch of complications.
            flags = pygame.DOUBLEBUF | pygame.FULLSCREEN | pygame.SCALED

            # Get biggest resolution for the active display
            modes = pygame.display.list_modes()
            size = modes[0]
            width, height = size

            self.screen = pygame.display.set_mode(size, flags)

            # Calculate scale factor
            scale_x = width / self.size[0]
            scale_y = height / self.size[1]
            self.model.scale = min(scale_x, scale_y)
        else:
            flags = pygame.DOUBLEBUF | pygame.SCALED
            self.screen = pygame.display.set_mode(self.size, flags)

            self.model.scale = 1

    def _update_network_settings(self) -> None:
        udp_ttl_ms = self.settings.get("udp_packet_ttl", 100)
        self.network_manager.update_ttl(udp_ttl_ms)

    def _update_connected(self, state: bool) -> None:
        self.model.control_connected = state
        self.event_controller.set_menu_tab_enabled("Streamer", self.model.control_connected)

    def _create_handlers(self) -> Dict[str, Any]:
        """Create message and state handlers for the network manager."""
        return {
            "messages": [
                (Telemetry, lambda message, address: self.osd.message_handler(message)),
                (Latency, lambda message, address: self.osd.message_handler(message)),
            ],
            "states": [
                (State.CONNECTED, lambda: self.osd.connect_handler()),
                (State.DISCONNECTED, lambda: self.osd.disconnect_handler()),
                (State.CONNECTED, lambda: self._update_connected(True)),
                (State.DISCONNECTED, lambda: self._update_connected(False))
            ]
        }

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

    def _send_control_message(self) -> None:
        """Send control message to streamer."""
        if (
            self.network_manager.server and
            not self.network_manager.server_error
        ):
            self.network_manager.server.send(Control({
                "steering": self.model.steering,
                "throttle": self.model.throttle,
            }))
