from collections import deque
import pygame
from typing import Tuple

from ui.helpers import get_fps, interpolate_steering_color, interpolate_throttle_color
from ui.Init import Init
from ui.KeyAxisHandler import KeyAxisHandler
from ui.widgets import VerticalIndicatorWidget, HorizontalIndicatorWidget
from ui.widgets import StatusValueWidget, FpsWidget


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
        self.throttle = 0.0
        self.steering = 0.0
        self.menu = None
        self.running = True

        self.screen, self.clock = Init.ui(self.size, self.title)
        self.video_receiver = Init.video_receiver(self.video_port)
        self.server, self.server_error = Init.server(control_port,
                                                     server_handlers)

        self.data = "waiting"

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
                range_mode="positive",
                color_fn=interpolate_throttle_color
            ),
            "data": StatusValueWidget(position=(10, 180),
                                      size=20,
                                      label="Data")
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
          )
        }
        self.key_handlers = {
            "throttle": KeyAxisHandler(
                positive=self.controls["throttle_up"],
                negative=self.controls["throttle_down"],
                step=self.throttle_settings["step"],
                friction=self.throttle_settings["friction"],
                min_val=0.0,
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

    @property
    def fps_loop(self) -> float:
        return get_fps(self.loop_history)

    @property
    def fps_video(self) -> float:
        return get_fps(self.video_receiver.history)

    def shutdown(self):
        pygame.quit()

        if self.server:
            self.server.stop()
            self.server.join()

        self.video_receiver.stop()
        self.video_receiver.join()
