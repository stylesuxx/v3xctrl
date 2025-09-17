from collections import deque
import logging
import pygame
import time
from typing import Optional, Tuple

from v3xctrl_control.message import Message, Latency, Telemetry
from v3xctrl_ui.colors import RED, WHITE
from v3xctrl_ui.helpers import (
  get_fps,
  interpolate_steering_color,
  interpolate_throttle_color
)
from v3xctrl_ui.Settings import Settings
from v3xctrl_ui.widgets import (
    Widget,
    Alignment,
    FpsWidget,
    HorizontalIndicatorWidget,
    StatusValueWidget,
    SignalQualityWidget,
    TextWidget,
    VerticalIndicatorWidget,
)


class OSD:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.width = self.settings.get("video").get("width")
        self.height = self.settings.get("video").get("height")

        self.widget_settings = None
        self.fps_settings = None
        self.update_settings(settings)

        self.widgets_debug = {}
        self.debug_data: Optional[str] = None
        self.debug_latency: Optional[str] = None
        self.loop_history: Optional[deque[float]] = None
        self.video_history: Optional[deque[float]] = None
        self._init_widgets_debug()

        self.widgets_signal = {}
        self.signal_quality: dict[str, int] = {"rsrq": -1, "rsrp": -1}
        self.signal_band: str = "Band ?"
        self._init_widgets_signal()

        self.widgets_battery = {}
        self.battery_voltage: str = "0.00V"
        self.battery_average_voltage: str = "0.00V"
        self.battery_percent: str = "100%"
        self._init_widgets_battery()

        self.widgets_steering = {}
        self.throttle: float = 0.0
        self.steering: float = 0.0
        self._init_widgets_steering()

        self.reset()

        self.widgets = self.widgets_steering

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.widget_settings = self.settings.get("widgets", {})

    def message_handler(self, message: Message) -> None:
        if isinstance(message, Telemetry):
            self._telemetry_update(message)
        elif isinstance(message, Latency):
            self._latency_update(message)

    def connect_handler(self) -> None:
        self.debug_data = "success"

    def disconnect_handler(self) -> None:
        self.reset()

    def set_control(self, throttle: float, steering: float) -> None:
        self.throttle = throttle
        self.steering = steering

    def update_data_queue(self, data_left: int) -> None:
        self.widgets_debug["debug_data"].set_value(data_left)

    def update_debug_status(self, status: str) -> None:
        self.debug_data = status

    @property
    def debug_fps_loop(self) -> float:
        return get_fps(self.loop_history)

    @property
    def debug_fps_video(self) -> float:
        if self.video_history is None:
            return 0.0

        return get_fps(self.video_history)

    def render(
            self,
            screen: pygame.Surface,
            loop_history: deque[float],
            video_history: deque[float] | None
    ) -> None:
        self.loop_history = loop_history
        self.video_history = video_history

        for name, widget in self.widgets.items():
            settings = self.widget_settings.get(name, {
                "align": None,
                "offset": (0, 0),
                "display": False
            })
            if settings.get("display"):
                align = settings.get("align")
                offset = settings.get("offset", (0, 0))
                position = self._get_position(align, widget, offset)

                widget.position = position
                widget.draw(screen, getattr(self, name))

        # Battery information widget
        index = 0
        align = self.widget_settings.get('battery', {"align": None}).get("align")
        offset = self.widget_settings.get('battery', {"offset": (0, 0)}).get("offset")
        for name, widget in self.widgets_battery.items():
            display = self.widget_settings.get(name, {"display": True}).get("display")

            if display:
                position = self._get_position(align, widget, offset)
                widget.position = (
                    position[0],
                    position[1] + 18 * index
                )
                widget.draw(screen, getattr(self, name))

                index += 1

        # Signal information widget
        settings = self.widget_settings.get('signal', {
            "align": None,
            "offset": (0, 0),
            "padding": 5,
            "display": False
        })
        if settings.get("display"):
            align = settings.get("align")
            offset = settings.get("offset", (0, 0))
            padding = settings.get("padding", 0)
            height = 0
            for name, widget in self.widgets_signal.items():
                display = self.widget_settings.get(name, {"display": True}).get("display")
                if display:
                    position = self._get_position(align, widget, offset)
                    widget.position = (
                        position[0],
                        position[1] + height
                    )
                    widget.draw(screen, getattr(self, name))
                    height += widget.height + padding

        # Debug widgets
        settings = self.widget_settings.get('debug', {
            "align": None,
            "offset": (0, 0),
            "padding": 5,
            "display": False
        })
        if settings.get("display"):
            align = settings.get("align")
            offset = settings.get("offset", (0, 0))
            padding = settings.get("padding", 0)
            height = 0
            for name, widget in self.widgets_debug.items():
                display = self.widget_settings.get(name, {"display": True}).get("display")
                if display:
                    position = self._get_position(align, widget, offset)
                    widget.position = (
                        position[0],
                        position[1] + height
                    )
                    widget.draw(screen, getattr(self, name))
                    height += widget.height + padding

    def _get_position(
        self,
        alignment: str,
        widget: Widget,
        offset: Tuple[int, int] = (0, 0)
    ) -> Tuple[int, int]:
        """
        Offset is always relative to the alignment, so if the alignment is
        top-left the offset is from (top, left), bottom-right is (bottom, right)
        """
        width, height = pygame.display.get_window_size()

        if alignment == "top-left":
            return offset

        elif alignment == "top-right":
            position = (width, 0)
            position = (position[0] - offset[1] - widget.width, position[1] + offset[0])

            return position

        elif alignment == "bottom-left":
            position = (0, height)
            position = (position[0] + offset[1], position[1] - offset[0] - widget.height)

            return position

        elif alignment == "bottom-right":
            position = (width, height)
            position = (position[0] - offset[1] - widget.width, position[1] - offset[0] - widget.height)

            return position

        elif alignment == "bottom-center":
            position = (width // 2, height)
            position = (position[0] - offset[1] - (widget.width // 2), position[1] - offset[0] - widget.height)

            return position

        return (0, 0)

    def reset(self) -> None:
        self.debug_data = "waiting"
        self.widgets_debug["debug_latency"].set_value(None)

        self.signal_quality = {"rsrq": -1, "rsrp": -1}

        self.battery_voltage = "0.00V"
        self.battery_average_voltage = "0.00V"
        self.battery_percent = "100%"
        self.battery_warn = False

        self.throttle = 0.0
        self.steering = 0.0

    def _init_widgets_steering(self) -> None:
        # Positions will be set during render

        steering_widget = HorizontalIndicatorWidget(
            position=(0, 0),
            size=(412, 22),
            bar_size=(20, 10),
            range_mode="symmetric",
            color_fn=interpolate_steering_color
        )

        throttle_widget = VerticalIndicatorWidget(
            position=(0, 0),
            size=(32, 212),
            bar_width=20,
            range_mode="symmetric",
            color_fn=interpolate_throttle_color
        )

        self.widgets_steering["steering"] = steering_widget
        self.widgets_steering["throttle"] = throttle_widget

    def _init_widgets_battery(self) -> None:
        # Position will be updated during rendering
        position = (0, 0)

        battery_voltage_widget = TextWidget(position, 70)
        battery_average_voltage_widget = TextWidget(position, 70)
        battery_percent_widget = TextWidget(position, 70)

        battery_voltage_widget.set_alignment(Alignment.RIGHT)
        battery_average_voltage_widget.set_alignment(Alignment.RIGHT)
        battery_percent_widget.set_alignment(Alignment.RIGHT)

        self.widgets_battery = {
            "battery_voltage": battery_voltage_widget,
            "battery_average_voltage": battery_average_voltage_widget,
            "battery_percent": battery_percent_widget
        }

    def _init_widgets_signal(self) -> None:
        # Position will be updated during rendering
        position = (0, 0)

        signal_quality_widget = SignalQualityWidget(position, (70, 50))
        signal_band_widget = TextWidget(position, 70)

        self.widgets_signal = {
            "signal_quality": signal_quality_widget,
            "signal_band": signal_band_widget
        }

    def _init_widgets_debug(self) -> None:
        # Position will be updated during rendering
        position = (0, 0)

        width = self.widget_settings["fps"].get("width")
        height = self.widget_settings["fps"].get("height")

        debug_fps_loop_widget = FpsWidget(position, (width, height), "Loop")
        debug_fps_video_widget = FpsWidget(position, (width, height), "Video")
        debug_data_widget = StatusValueWidget(position, 26, "Data")
        debug_latency_widget = StatusValueWidget(position, 26, "Latency")

        self.widgets_debug = {
          "debug_fps_loop": debug_fps_loop_widget,
          "debug_fps_video": debug_fps_video_widget,
          "debug_data": debug_data_widget,
          "debug_latency": debug_latency_widget
        }

    def _latency_update(self, message: Latency) -> None:
        """
        NOTE: We rely on the streamer and viewer to have the same timezone set
              and do not account for any form of drift.
        """
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

    def _telemetry_update(self, message: Telemetry) -> None:
        values = message.get_values()

        # Signal quality & band
        self.signal_quality = {
            "rsrq": values["sig"]["rsrq"],
            "rsrp": values["sig"]["rsrp"],
        }
        band = values["cell"]["band"]
        self.signal_band = f"Band {band}"

        # Battery
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
