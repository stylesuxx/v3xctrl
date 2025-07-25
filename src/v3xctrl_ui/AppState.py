from collections import deque
import logging
import pygame
import socket
import threading
import time
from typing import Tuple

from v3xctrl_control.Message import Message, Telemetry, Latency, Control
from v3xctrl_helper.exceptions import UnauthorizedError
from v3xctrl_ui.colors import RED, WHITE
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
  Alignment
)
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
        self.fps_settings = None
        self.control_settings = None
        self.throttle_settings = None
        self.steering_settings = None
        self.widget_settings = None
        self.update_settings(self.settings)

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

        # Data for widgets_debug
        self.debug_data = None
        self.debug_latency = None

        # Data for widgets
        self.throttle = None
        self.steering = None
        self.signal_quality = None
        self.band = "Band ?"

        # Data for battery
        self.battery_voltage = None
        self.battery_average_voltage = None
        self.battery_percent = None

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

        battery_voltage_widget = TextWidget(
            (self.size[0] - 70 - 10, 10 + 50 + 25 + 18 * 0),
            70
        )
        battery_average_voltage_widget = TextWidget(
            (self.size[0] - 70 - 10, 10 + 50 + 25 + 18 * 1),
            70
        )
        battery_percent_widget = TextWidget(
            (self.size[0] - 70 - 10, 10 + 50 + 25 + 18 * 2),
            70
        )

        battery_voltage_widget.set_alignment(Alignment.RIGHT)
        battery_average_voltage_widget.set_alignment(Alignment.RIGHT)
        battery_percent_widget.set_alignment(Alignment.RIGHT)

        self.widgets_battery = {
            "battery_voltage": battery_voltage_widget,
            "battery_average_voltage": battery_average_voltage_widget,
            "battery_percent": battery_percent_widget
        }

        self.widgets_debug = {
          "debug_fps_loop": FpsWidget(
              (10, 10),
              (self.fps_settings["width"], self.fps_settings["height"]),
              "Loop"
          ),
          "debug_fps_video": FpsWidget(
              (10, 10 + self.fps_settings["height"] + 10),
              (self.fps_settings["width"], self.fps_settings["height"]),
              "Video"
          ),
          "debug_data": StatusValueWidget(
              position=(10, 180),
              size=26,
              label="Data"
          ),
          "debug_latency": StatusValueWidget(
              position=(10, 216),
              size=26,
              label="Latency"
          )
        }

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

    @property
    def debug_fps_loop(self) -> float:
        return get_fps(self.loop_history.copy())

    @property
    def debug_fps_video(self) -> float:
        if self.video_receiver is None:
            return 0.0

        return get_fps(self.video_receiver.history.copy())

    def reset_data(self) -> None:
        # Data for widgets_debug
        self.debug_data = "waiting"
        self.debug_latency = "default"

        # Data for widgets
        self.throttle = 0.0
        self.steering = 0.0
        self.signal_quality = {
            "rsrq": -1,
            "rsrp": -1,
        }

        # Data for battery
        self.battery_voltage = "0.00V"
        self.battery_average_voltage = "0.00V"
        self.battery_percent = "100%"
        self.battery_warn = False

        self.widgets_debug["debug_latency"].set_value(None)

    def _telemetry_update(self, message: Telemetry) -> None:
        values = message.get_values()
        self.signal_quality = {
            "rsrq": values["sig"]["rsrq"],
            "rsrp": values["sig"]["rsrp"],
        }
        band = values["cell"]["band"]
        self.band = f"Band {band}"

        battery_voltage = values["bat"]["vol"] / 1000
        battery_average_voltage = values["bat"]["avg"] / 1000
        battery_percentage = values["bat"]["pct"]

        self.battery_voltage = f"{battery_voltage:.2f}V"
        self.battery_average_voltage = f"{battery_average_voltage:.2f}V"
        self.battery_percent = f"{battery_percentage}%"

        widgets_battery = [
            "battery_voltage",
            "battery_average_voltage",
            "battery_percent"
        ]

        color = WHITE
        if values["bat"]["wrn"]:
            color = RED

        for widget in widgets_battery:
            self.widgets_battery[widget].set_text_color(color)

        logging.debug(f"Received telemetry message: {values}")

    def _latency_update(self, message: Latency) -> None:
        now = time.time()
        timestamp = message.timestamp
        diff_ms = round((now - timestamp) * 1000)

        if diff_ms <= 80:
            self.debug_latency = "green"
        elif diff_ms <= 150:
            self.debug_latency = "yellow"
        else:
            self.debug_latency = "red"

        self.widgets_debug["debug_latency"].set_value(diff_ms)
        logging.debug(f"Received latency message: {diff_ms}ms")

    def message_handler(self, message: Message) -> None:
        if isinstance(message, Telemetry):
            self._telemetry_update(message)
        elif isinstance(message, Latency):
            self._latency_update(message)

    def connect_handler(self):
        self.debug_data = "success"

    def disconnect_handler(self):
        self.reset_data()

    def update_settings(self, settings: Settings):
        self.settings = settings

        self.fps_settings = settings.get("widgets")["fps"]
        self.control_settings = settings.get("controls")["keyboard"]
        self.throttle_settings = settings.get("settings")["throttle"]
        self.steering_settings = settings.get("settings")["steering"]
        self.widget_settings = settings.get("widgets", {})

        self.menu = None

    def _update_data(self) -> None:
        if (
            self.server and
            not self.server_error
        ):
            data_left = self.server.transmitter.queue.qsize()
            self.widgets_debug["debug_data"].set_value(data_left)
        else:
            self.debug_data = "fail"

    def handle_control(self, pressed_keys, gamepad_inputs) -> None:
        self._update_data()

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

    def render_widgets(self):
        for name, widget in self.widgets.items():
            display = self.widget_settings.get(name, {"display": True}).get("display")
            if display:
                widget.draw(self.screen, getattr(self, name))

        index = 0
        for name, widget in self.widgets_battery.items():
            display = self.widget_settings.get(name, {"display": True}).get("display")
            if display:
                widget.position = (self.size[0] - 70 - 10, 10 + 50 + 25 + 18 * index)
                widget.draw(self.screen, getattr(self, name))

                index += 1

        debug = self.widget_settings.get("debug", {"display": False}).get("display")
        if debug:
            for name, widget in self.widgets_debug.items():
                display = self.widget_settings.get(name, {"display": True}).get("display")
                if display:
                    widget.draw(self.screen, getattr(self, name))

    def shutdown(self):
        pygame.quit()

        if self.server:
            self.server.stop()
            self.server.join()

        if self.video_receiver:
            self.video_receiver.stop()
            self.video_receiver.join()
