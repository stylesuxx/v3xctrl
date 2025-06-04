from collections import deque
import logging
import pygame
import socket
import threading
from time import sleep
from typing import Tuple

from v3xctrl_ui.helpers import get_fps, interpolate_steering_color, interpolate_throttle_color
from v3xctrl_ui.Init import Init
from v3xctrl_ui.KeyAxisHandler import KeyAxisHandler
from v3xctrl_ui.widgets import (
  VerticalIndicatorWidget,
  HorizontalIndicatorWidget,
  StatusValueWidget,
  FpsWidget,
  SignalQualityWidget,
  TextWidget,
)

from v3xctrl_udp_relay.Peer import Peer


class AppState:
    """
    Holds the current context of the app.
    """
    def __init__(self,
                 size: Tuple[int, int],
                 title: str,
                 video_port: int,
                 control_port: int,
                 server_handlers: dict,
                 fps_settings: dict,
                 controls: dict,
                 throttle_settings: dict,
                 steering_settings: dict):
        self.size = size
        self.title = title
        self.video_port = video_port
        self.control_port = control_port
        self.server_handlers = server_handlers
        self.fps_settings = fps_settings
        self.controls = controls
        self.throttle_settings = throttle_settings
        self.steering_settings = steering_settings

        self.loop_history = deque(maxlen=300)
        self.menu = None
        self.running = True

        self.screen, self.clock = Init.ui(self.size, self.title)

        self.video_receiver = None
        self.server_error = None
        self.server = None

        self.relay_enable = False
        self.relay_server = None
        self.relay_port = 8888
        self.relay_id = None

        # Data for widgets_debug
        self.data = None
        self.latency = None

        # Data for widgets
        self.throttle = None
        self.steering = None
        self.signal_quality = None
        self.band = "Band ?"

        self.widgets = {
            "steering": HorizontalIndicatorWidget(
                pos=(self.size[0] // 2 - 200 - 6, self.size[1] - 30 - 6),
                size=(412, 22),
                bar_size=(20, 10),
                range_mode="symmetric",
                color_fn=interpolate_steering_color
            ),
            "throttle": VerticalIndicatorWidget(
                pos=(14, self.size[1] - 200 - 20 - 6),
                size=(32, 212),
                bar_width=20,
                range_mode="symmetric",
                color_fn=interpolate_throttle_color
            ),
            "signal_quality": SignalQualityWidget(
                (self.size[0] - 70 - 10, 10),
                (70, 50)
            ),
            "band": TextWidget(
                (self.size[0] - 70 - 10, 10 + 50),
                70
            )
        }

        self.widgets_debug = {
          "fps_loop": FpsWidget(
              (10, 10),
              (self.fps_settings["width"], self.fps_settings["height"]),
              "Loop"
          ),
          "fps_video": FpsWidget(
              (10, 10 + self.fps_settings["height"] + 10),
              (self.fps_settings["width"], self.fps_settings["height"]),
              "Video"
          ),
          "data": StatusValueWidget(
              position=(10, 180),
              size=26,
              label="Data"
          ),
          "latency": StatusValueWidget(
              position=(10, 216),
              size=26,
              label="Latency"
          )
        }

        self.key_handlers = {
            "throttle": KeyAxisHandler(
                positive=self.controls["throttle_up"],
                negative=self.controls["throttle_down"],
                step=self.throttle_settings["step"],
                friction=self.throttle_settings["friction"],
                min_val=-1.0,
                max_val=1.0
            ),
            "steering": KeyAxisHandler(
                positive=self.controls["steering_right"],
                negative=self.controls["steering_left"],
                step=self.steering_settings["step"],
                friction=self.steering_settings["friction"],
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
                addresses = peer.setup("viewer", local_bind_ports)
                video_address = addresses["video"]

            def poke_peer():
                logging.info(f"Poking peer {video_address}")
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("0.0.0.0", self.video_port))

                    for i in range(5):
                        try:
                            sock.sendto(b'SYN', video_address)
                            sleep(0.1)
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

    @property
    def fps_loop(self) -> float:
        return get_fps(self.loop_history.copy())

    @property
    def fps_video(self) -> float:
        if self.video_receiver is None:
            return 0.0

        return get_fps(self.video_receiver.history.copy())

    def reset_data(self) -> None:
        # Data for widgets_debug
        self.data = "waiting"
        self.latency = "default"

        # Data for widgets
        self.throttle = 0.0
        self.steering = 0.0
        self.signal_quality = {
            "rsrq": -1,
            "rsrp": -1,
        }

        self.widgets_debug["latency"].set_value(None)

    def shutdown(self):
        pygame.quit()

        if self.server:
            self.server.stop()
            self.server.join()

        if self.video_receiver:
            self.video_receiver.stop()
            self.video_receiver.join()
