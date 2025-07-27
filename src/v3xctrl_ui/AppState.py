from collections import deque
import logging
import pygame
import socket
import threading
import time
from typing import Tuple

from v3xctrl_control.Message import Message, Control
from v3xctrl_helper.exceptions import UnauthorizedError
from v3xctrl_ui.Init import Init
from v3xctrl_ui.KeyAxisHandler import KeyAxisHandler
from v3xctrl_ui.OSD import OSD
from v3xctrl_ui.Settings import Settings

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
        server_handlers: dict,
        settings: Settings
    ):
        self.size = size
        self.title = title
        self.video_port = video_port
        self.control_port = control_port
        self.server_handlers = server_handlers

        # Initialize settings
        self.settings = settings
        self.control_settings = None

        self.loop_history = deque(maxlen=300)
        self.menu = None
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

        self.osd = OSD(settings)

        self.update_settings(self.settings)

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

        self.reset_data()

    def setup_relay(self, relay_server: str = None, relay_id: str = None) -> None:
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

    def setup_ports(self):
        def task():
            if self.relay_enable:
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

            def poke_peer():
                if self.relay_enable:
                    logging.info(f"Poking peer {video_address}")
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
                        sock.close()
                        logging.info(f"Poke to {video_address} completed and socket closed.")

            self.video_receiver = Init.video_receiver(self.video_port, poke_peer)
            self.server, self.server_error = Init.server(self.control_port,
                                                         self.server_handlers)

            logging.info("Port setup complete.")

        threading.Thread(target=task, daemon=True).start()

    def reset_data(self) -> None:
        self.osd.reset()

    def message_handler(self, message: Message) -> None:
        self.osd.message_handler(message)

    def connect_handler(self):
        self.osd.connect_handler()

    def disconnect_handler(self):
        self.osd.disconnect_handler()

    def update_settings(self, settings: Settings):
        self.settings = settings

        self.control_settings = settings.get("controls")["keyboard"]

        self.osd.update_settings(settings)

        self.menu = None

    def _update_data(self) -> None:
        if (
            self.server and
            not self.server_error
        ):
            data_left = self.server.transmitter.queue.qsize()
            self.osd.widgets_debug["debug_data"].set_value(data_left)
        else:
            self.osd.debug_data = "fail"

    def handle_control(self, pressed_keys, gamepad_inputs) -> None:
        self._update_data()

        self.throttle = self.key_handlers["throttle"].update(pressed_keys)
        self.steering = self.key_handlers["steering"].update(pressed_keys)

        if gamepad_inputs:
            self.steering = gamepad_inputs["steering"]

            throttle = gamepad_inputs["throttle"]
            brake = gamepad_inputs["brake"]
            self.throttle = (throttle - brake)

        self.osd.steering = self.steering
        self.osd.throttle = self.throttle

        if self.server and not self.server_error:
            self.server.send(Control({
                "steering": self.steering,
                "throttle": self.throttle,
            }))

    def render_widgets(self):
        video_history = None
        if self.video_receiver is not None:
            video_history = self.video_receiver.history.copy()

        self.osd.render(
            self.screen,
            self.loop_history.copy(),
            video_history
        )

    def shutdown(self):
        pygame.quit()

        if self.server:
            self.server.stop()
            self.server.join()

        if self.video_receiver:
            self.video_receiver.stop()
            self.video_receiver.join()
