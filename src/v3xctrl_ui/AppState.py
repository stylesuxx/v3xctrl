from collections import deque
import logging
import signal
import time
from typing import Any, Dict, Optional, Tuple

import pygame

from v3xctrl_control import State
from v3xctrl_control.message import Control, Latency, Telemetry

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
    def __init__(
        self,
        size: Tuple[int, int],
        title: str,
        video_port: int,
        control_port: int,
        settings: Settings
    ) -> None:
        self.size = size
        self.title = title
        self.video_port = video_port
        self.control_port = control_port

        self.settings = settings

        self.scale = 1
        self.fullscreen = self.settings.get(
            "video",
            {"fullscreen": False}
        ).get("fullscreen", False)

        self.input_manager = InputManager(settings)

        self.osd = OSD(settings)
        self.renderer = Renderer(self.size, self.settings)

        self.control_connected = False

        handlers = self._create_handlers()
        self.network_manager = NetworkManager(
            video_port,
            control_port,
            self.settings,
            handlers
        )

        # Timing
        self.control_interval = 0.0
        self.latency_interval = 0.0
        self.last_control_update = 0.0
        self.last_latency_check = 0.0
        self._update_timing_settings()

        self.loop_history: deque[float] = deque(maxlen=300)
        self.menu: Optional[Menu] = None
        self.running = True

        self.screen, self.clock = Init.ui(self.size, self.title)
        if self.fullscreen:
            self._update_screen_size()

        self.throttle: float = 0
        self.steering: float = 0

        self._setup_signal_handling()

        self.network_manager.setup_ports()

    def initialize_timing(self, start_time: float) -> None:
        """Initialize timing counters."""
        self.last_control_update = start_time
        self.last_latency_check = start_time

    def update_settings(self, settings: Optional[Settings] = None) -> None:
        """
        Update settings after exiting menu.
        Only update settings that can be hot reloaded.
        """
        if settings is None:
            settings = Init.settings("settings.toml")

        self.settings = settings

        self._update_timing_settings()

        # Attempt fullscreen/window switch only if the setting actually changed
        fullscreen_previous = self.fullscreen
        self.fullscreen = self.settings.get("video", {"fullscreen": False}).get("fullscreen")
        if fullscreen_previous is not self.fullscreen:
            self._update_screen_size()

        self.input_manager.update_settings(settings)
        self.osd.update_settings(settings)
        self.renderer.settings = settings

        # Clear menu to force refresh
        self.menu = None

    def update(self, now: float) -> None:
        """Update application state with timed operations."""
        # Handle control updates
        if now - self.last_control_update >= self.control_interval:
            try:
                self.throttle, self.steering = self.input_manager.read_inputs()
                self._send_control_message()
            except Exception as e:
                logging.warning(f"Input read error: {e}")
            self.last_control_update = now

        # Handle latency checks
        if now - self.last_latency_check >= self.latency_interval:
            self.network_manager.send_latency_check()
            self.last_latency_check = now

    def handle_events(self) -> bool:
        """
        Handle pygame events. Returns False if application should quit.
        """
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
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
                    else:
                        # When exiting vie [ESC], do the same thing we would do
                        # when using the "Back" button from the menu
                        self.update_settings()

                # [F11] - Toggle Fullscreen
                elif event.key == pygame.K_F11:
                    self.fullscreen = not self.fullscreen
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

        self.osd.update_data_queue(data_left)
        self.osd.set_control(self.throttle, self.steering)

        self.renderer.render_all(
            self,
            self.network_manager,
            self.fullscreen,
            self.scale
        )

    def shutdown(self) -> None:
        logging.info("Shutting down...")
        pygame.quit()

        start = time.monotonic()
        self.input_manager.shutdown()
        delta = round(time.monotonic() - start)
        logging.debug(f"Input manager shut down after {delta}s")

        start = time.monotonic()
        self.network_manager.shutdown()
        delta = round(time.monotonic() - start)
        logging.debug(f"Network manager shut down after {delta}s")

    def _update_screen_size(self) -> None:
        if self.fullscreen:
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
            self.scale = min(scale_x, scale_y)
        else:
            flags = pygame.DOUBLEBUF | pygame.SCALED
            self.screen = pygame.display.set_mode(self.size, flags)

            self.scale = 1

    def _update_connected(self, state: bool) -> None:
        self.control_connected = state

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
        if self.running:
            self.running = False

    def _update_timing_settings(self) -> None:
        """Update timing intervals from settings."""
        timing = self.settings.get("timing", {})
        control_rate_frequency = timing.get("control_update_hz", 30)
        latency_check_frequency = timing.get("latency_check_hz", 1)

        self.control_interval = 1.0 / control_rate_frequency
        self.latency_interval = 1.0 / latency_check_frequency

    def _send_control_message(self) -> None:
        """Send control message to streamer."""
        if self.network_manager.server and not self.network_manager.server_error:
            self.network_manager.server.send(Control({
                "steering": self.steering,
                "throttle": self.throttle,
            }))
