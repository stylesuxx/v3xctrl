import copy
import logging
import signal
import threading
import time
from typing import Any, Dict, Optional

import pygame

from v3xctrl_control import State
from v3xctrl_control.message import Control, Latency, Telemetry

from v3xctrl_ui.ApplicationModel import ApplicationModel
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
        self.main_loop_fps = 60
        self._update_timing_settings()

        self.menu: Optional[Menu] = None

        self.screen, self.clock = Init.ui(self.size, self.title)
        if self.model.fullscreen:
            self._update_screen_size()

        self._setup_signal_handling()

        self.network_manager.setup_ports()

        start_time = time.monotonic()
        self.model.last_control_update = start_time
        self.model.last_latency_check = start_time

        # Deep copy of current settings so we can later easily check if settings
        # need updating.
        self.old_settings = copy.deepcopy(self.settings)

        # Network restart state
        self.network_restart_thread: Optional[threading.Thread] = None
        self.network_restart_complete = threading.Event()

    def update_settings(self, new_settings: Optional[Settings] = None) -> None:
        """
        Update settings after exiting menu.
        Only update settings that can be hot reloaded.
        """
        if new_settings is None:
            new_settings = Init.settings("settings.toml")

        # Attempt fullscreen/window switch only if the setting actually changed
        fullscreen_previous = self.model.fullscreen
        self.model.fullscreen = new_settings.get("video", {}).get("fullscreen", False)
        if fullscreen_previous is not self.model.fullscreen:
            self._update_screen_size()

        # Check if network manager needs to be restarted
        if (
            not self._settings_equal(new_settings, "ports") or
            not self._settings_equal(new_settings, "relay")
        ):
            logging.info("Restarting network manager")
            self.model.pending_settings = new_settings
            self.network_manager.shutdown()
            self.network_manager = NetworkManager(
                new_settings,
                self.handlers
            )
            self.network_restart_thread.start()
            return

        # Apply settings immediately if no network restart needed
        self._apply_settings(new_settings)

    def update(self) -> None:
        """Update application state with timed operations."""
        # Check if network restart is complete
        if self.network_restart_complete.is_set():
            self.network_restart_complete.clear()

            if self.model.pending_settings:
                self._apply_settings(self.model.pending_settings)
                self.model.pending_settings = None

            logging.info("Network manager restart complete")

        now = time.monotonic()
        self.model.loop_history.append(now)

        # Handle control updates, send last values if user is in menu
        if now - self.model.last_control_update >= self.model.control_interval:
            try:
                throttle, steering = (0, 0)
                if not self.menu:
                    throttle, steering = self.input_manager.read_inputs()

                self.model.throttle = throttle
                self.model.steering = steering

                self._send_control_message()
            except Exception as e:
                logging.warning(f"Input read error: {e}")
            self.model.last_control_update = now

        # Handle latency checks
        if now - self.model.last_latency_check >= self.model.latency_interval:
            self.network_manager.send_latency_check()
            self.model.last_latency_check = now

    def tick(self) -> None:
        self.clock.tick(self.main_loop_fps)

    def handle_events(self) -> bool:
        """
        Handle pygame events. Returns False if application should quit.
        """
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.model.running = False
                return False

            elif event.type == pygame.KEYDOWN:

                # [ESC] - Toggle Menu
                if event.key == pygame.K_ESCAPE:
                    if self.menu is None:
                        self.menu = Menu(
                            self.screen.get_size()[0],
                            self.screen.get_size()[1],
                            self.input_manager.gamepad_manager,
                            self.settings,
                            self.network_manager.server,
                            self.update_settings,
                            self._signal_handler
                        )

                        self.menu.set_tab_enabled("Streamer", self.model.control_connected)
                    else:
                        if not self.menu.is_loading:
                            # When exiting vie [ESC], do the same thing we would do
                            # when using the "Back" button from the menu
                            self.update_settings()

                # [F11] - Toggle Fullscreen
                elif event.key == pygame.K_F11:
                    self.model.fullscreen = not self.model.fullscreen
                    self._update_screen_size()

            if self.menu is not None:
                self.menu.handle_event(event)

        return True

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
        if self.network_restart_thread and self.network_restart_thread.is_alive():
            logging.info("Waiting for network restart to complete...")
            self.network_restart_thread.join(timeout=5.0)

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
            self.network_restart_complete.set()

    def _apply_settings(self, new_settings: Settings) -> None:
        """Apply new settings to all components."""
        # Update new settings to settings and trigger updates on elements who
        # need to handle new settings
        self.settings = new_settings
        self.old_settings = copy.deepcopy(self.settings)

        self._update_timing_settings()
        self._update_network_settings()

        self.input_manager.update_settings(self.settings)
        self.osd.update_settings(self.settings)
        self.renderer.settings = self.settings

        # Clear menu to force refresh
        self.menu = None

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

    def _update_timing_settings(self) -> None:
        """Update timing intervals from settings."""
        timing = self.settings.get("timing", {})
        control_rate_frequency = timing.get("control_update_hz", 30)
        latency_check_frequency = timing.get("latency_check_hz", 1)

        self.model.control_interval = 1.0 / control_rate_frequency
        self.model.latency_interval = 1.0 / latency_check_frequency
        self.main_loop_fps = timing.get("main_loop_fps", 60)

    def _update_network_settings(self) -> None:
        udp_ttl_ms = self.settings.get("udp_packet_ttl", 100)
        self.network_manager.update_ttl(udp_ttl_ms)

    def _update_connected(self, state: bool) -> None:
        self.model.control_connected = state
        if self.menu:
            self.menu.set_tab_enabled("Streamer", self.model.control_connected)

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
        self.menu = None
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

    def _settings_equal(self, settings: Settings, key: str) -> bool:
        old_settings = self.old_settings.get(key)
        new_settings = settings.get(key)

        if new_settings.keys() != old_settings.keys():
            return False

        for key in old_settings:
            if new_settings.get(key) != old_settings.get(key):
                return False

        return True
