from collections import deque
import logging
import pygame
from pygame.key import ScancodeWrapper
import socket
import threading
import time
from typing import Tuple, Optional, Dict, Any

from v3xctrl_control.message import Control
from v3xctrl_helper.exceptions import UnauthorizedError
from v3xctrl_ui.Init import Init
from v3xctrl_ui.KeyAxisHandler import KeyAxisHandler
from v3xctrl_ui.Settings import Settings

from v3xctrl_udp_relay.Peer import Peer

from v3xctrl_ui.menu.Menu import Menu


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
        server_handlers: Dict[str, Any],
        settings: Settings
    ) -> None:
        self.size = size
        self.title = title
        self.video_port = video_port
        self.control_port = control_port
        self.server_handlers = server_handlers

        # Initialize settings
        self.settings = settings
        self.control_settings = None

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

    def setup_ports(self) -> None:
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

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings

        self.control_settings = settings.get("controls")["keyboard"]

        self.menu = None

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

    def shutdown(self) -> None:
        pygame.quit()

        if self.server:
            self.server.stop()
            self.server.join()

        if self.video_receiver:
            self.video_receiver.stop()
            self.video_receiver.join()
