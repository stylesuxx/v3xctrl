from collections import deque
import logging
import pygame
from pygame.key import ScancodeWrapper
import socket
import threading
import time
from typing import Tuple, Optional, Dict, Any

from v3xctrl_control.message import Control, Telemetry, Latency

from v3xctrl_helper.exceptions import UnauthorizedError
from v3xctrl_ui.helpers import get_external_ip

from v3xctrl_control import State

from v3xctrl_ui.GamepadManager import GamepadManager
from v3xctrl_ui.Init import Init
from v3xctrl_ui.KeyAxisHandler import KeyAxisHandler
from v3xctrl_ui.OSD import OSD
from v3xctrl_ui.Renderer import Renderer
from v3xctrl_ui.Settings import Settings
from v3xctrl_ui.menu.Menu import Menu

from v3xctrl_udp_relay.Peer import Peer


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

        # Initialize settings
        self.settings = settings
        self.control_settings = None

        # Initialize and setup gamepad manager
        self.gamepad_manager = GamepadManager()
        self._setup_gamepad_manager()

        self.osd = OSD(settings)

        self.renderer = Renderer(self.size, self.settings)

        self.server_handlers = self._create_handlers()

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

        self.video_receiver = None
        self.server_error = None
        self.server = None

        self.relay_status_message = "Waiting for streamer..."
        self.relay_enable = False
        self.relay_server = None
        self.relay_port = 8888
        self.relay_id = None

        self.throttle: float = 0
        self.steering: float = 0

        self.update_settings(self.settings)

        if self.control_settings:
            self.key_handlers = {
                "throttle": KeyAxisHandler(
                    positive=self.control_settings["throttle_up"],
                    negative=self.control_settings["throttle_down"],
                    min_val=-1.0,
                    max_val=1.0
                ),
                "steering": KeyAxisHandler(
                    positive=self.control_settings["steering_right"],
                    negative=self.control_settings["steering_left"],
                    min_val=-1.0,
                    max_val=1.0
                )
            }

        self._setup_relay_if_enabled()
        self._print_connection_info_if_needed()

        self._setup_signal_handling()

        self._setup_ports()

    def _setup_signal_handling(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        import signal
        signal.signal(signal.SIGINT, self._signal_handler)

    def _setup_relay_if_enabled(self) -> None:
        """Setup relay connection if enabled in settings."""
        relay = self.settings.get("relay", {})
        if relay.get("enabled", False):
            server = relay.get("server")
            relay_id = relay.get("id")
            if server and relay_id:
                self.setup_relay(server, relay_id)

    def _print_connection_info_if_needed(self) -> None:
        """Print connection info to console if not using relay."""
        relay = self.settings.get("relay", {})
        if not relay.get("enabled", False):
            ip = get_external_ip()
            ports = self.settings.get("ports")

            print("================================")
            print(f"IP Address:   {ip}")
            print(f"Video port:   {ports['video']}")
            print(f"Control port: {ports['control']}")
            print("Make sure to forward this ports!")
            print("================================")

    def _signal_handler(self, sig: Any, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        if self.running:
            self.running = False
            print("Shutting down...")

    def _setup_gamepad_manager(self) -> None:
        """Setup gamepad manager with calibrations and active gamepad."""
        calibrations = self.settings.get("calibrations", {})
        for guid, calibration in calibrations.items():
            self.gamepad_manager.set_calibration(guid, calibration)

        input_settings = self.settings.get("input", {})
        if "guid" in input_settings:
            self.gamepad_manager.set_active(input_settings["guid"])

        self.gamepad_manager.start()

    def _update_timing_settings(self) -> None:
        """Update timing intervals from settings."""
        timing = self.settings.get("timing", {})
        control_rate_frequency = timing.get("control_update_hz", 30)
        latency_check_frequency = timing.get("latency_check_hz", 1)

        self.control_interval = 1.0 / control_rate_frequency
        self.latency_interval = 1.0 / latency_check_frequency

    def _create_handlers(self) -> Dict[str, Any]:
        """Create message and state handlers for the server."""

        return {
            "messages": [
                (Telemetry, lambda message, address: self.osd.message_handler(message)),
                (Latency, lambda message, address: self.osd.message_handler(message)),
            ],
            "states": [
                (State.CONNECTED, lambda: self.osd.connect_handler()),
                (State.DISCONNECTED, lambda: self.osd.disconnect_handler())
            ]
        }

    def update(self, now: float) -> None:
        """Update application state with timed operations."""
        # Handle control updates
        if now - self.last_control_update >= self.control_interval:
            pressed_keys = pygame.key.get_pressed()
            gamepad_inputs = self.gamepad_manager.read_inputs()
            self.handle_control(pressed_keys, gamepad_inputs)
            self.last_control_update = now

        # Handle latency checks
        if now - self.last_latency_check >= self.latency_interval:
            if self.server and not self.server_error:
                from v3xctrl_control.message import Latency
                self.server.send(Latency())
            self.last_latency_check = now

    def initialize_timing(self, start_time: float) -> None:
        """Initialize timing counters."""
        self.last_control_update = start_time
        self.last_latency_check = start_time

    def setup_relay(
        self,
        relay_server: str,
        relay_id: str
    ) -> None:
        self.relay_enable = True
        self.relay_id = relay_id

        if relay_server and ':' in relay_server:
            host, port = relay_server.rsplit(':', 1)
            self.relay_server = host
            try:
                self.relay_port = int(port)
            except ValueError:
                logging.warning(f"Invalid port in relay_server: '{relay_server}', falling back to default {self.relay_port}")
        else:
            self.relay_server = relay_server

    def _setup_ports(self) -> None:
        def task() -> None:
            video_address = None
            if self.relay_enable and self.relay_server and self.relay_id:
                local_bind_ports = {
                    "video": self.video_port,
                    "control": self.control_port
                }
                peer = Peer(self.relay_server, self.relay_port, self.relay_id)

                try:
                    addresses = peer.setup("viewer", local_bind_ports)
                    video_address = addresses["video"]
                except UnauthorizedError:
                    self.relay_status_message = "ERROR: Relay ID unauthorized!"
                    return

            def poke_peer() -> None:
                if self.relay_enable and video_address:
                    logging.info(f"Poking peer {video_address}")
                    sock = None
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        sock.bind(("0.0.0.0", self.video_port))

                        for i in range(5):
                            try:
                                sock.sendto(b'SYN', video_address)
                                time.sleep(0.1)
                            except Exception as e:
                                logging.warning(f"Poke {i+1}/5 failed: {e}")

                    except Exception as e:
                        logging.error(f"Failed to poke peer: {e}", exc_info=True)
                    finally:
                        if sock:
                            sock.close()
                        logging.info(f"Poke to {video_address} completed and socket closed.")

            self.video_receiver = Init.video_receiver(self.video_port, poke_peer)
            self.server, self.server_error = Init.server(self.control_port,
                                                         self.server_handlers)

            logging.info("Port setup complete.")

        threading.Thread(target=task, daemon=True).start()

    def update_settings(self, settings: Optional[Settings] = None) -> None:
        """
        Update settings after exiting menu.
        Only update settings that can be hot reloaded.
        """
        if settings is None:
            settings = Init.settings("settings.toml")

        self.settings = settings

        # Update control settings
        self.control_settings = settings.get("controls")["keyboard"]

        # Update timing settings
        self._update_timing_settings()

        # Update key handlers if they exist
        if hasattr(self, 'key_handlers'):
            self.key_handlers = {
                "throttle": KeyAxisHandler(
                    positive=self.control_settings["throttle_up"],
                    negative=self.control_settings["throttle_down"],
                    min_val=-1.0,
                    max_val=1.0
                ),
                "steering": KeyAxisHandler(
                    positive=self.control_settings["steering_right"],
                    negative=self.control_settings["steering_left"],
                    min_val=-1.0,
                    max_val=1.0
                )
            }

        # Update gamepad calibrations
        calibrations = settings.get("calibrations", {})
        for guid, calibration in calibrations.items():
            self.gamepad_manager.set_calibration(guid, calibration)

        input_settings = settings.get("input", {})
        if "guid" in input_settings:
            self.gamepad_manager.set_active(input_settings["guid"])

        # Update OSD settings
        self.osd.update_settings(settings)

        # Update renderer settings
        self.renderer.settings = settings

        # Clear menu to force refresh
        self.menu = None

    def handle_events(self) -> bool:
        """
        Handle pygame events. Returns False if application should quit.
        """
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
                return False

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.menu is None:
                    self.menu = Menu(
                        self.size[0],
                        self.size[1],
                        self.gamepad_manager,
                        self.settings,
                        self.update_settings,
                        self.server
                    )
                else:
                    self.menu = None

            elif self.menu is not None:
                self.menu.handle_event(event)

        return True

    def handle_control(
        self,
        pressed_keys: ScancodeWrapper,
        gamepad_inputs: ScancodeWrapper
    ) -> None:
        self.throttle = self.key_handlers["throttle"].update(pressed_keys)
        self.steering = self.key_handlers["steering"].update(pressed_keys)

        if gamepad_inputs:
            self.steering = gamepad_inputs["steering"]

            throttle = gamepad_inputs["throttle"]
            brake = gamepad_inputs["brake"]
            self.throttle = (throttle - brake)

        if self.server and not self.server_error:
            self.server.send(Control({
                "steering": self.steering,
                "throttle": self.throttle,
            }))

    def render(self) -> None:
        self.renderer.render_all(self)

    def shutdown(self) -> None:
        self.gamepad_manager.stop()

        pygame.quit()

        if self.server:
            self.server.stop()
            self.server.join()

        if self.video_receiver:
            self.video_receiver.stop()
            self.video_receiver.join()
