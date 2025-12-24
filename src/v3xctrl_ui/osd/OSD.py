from collections import deque
import logging
import pygame
import time
from typing import (
  Optional,
  Dict,
  List,
)

from v3xctrl_control.message import Message, Latency, Telemetry
from v3xctrl_ui.utils.colors import RED, WHITE
from v3xctrl_ui.osd.TelemetryParser import TelemetryParser
from v3xctrl_ui.utils.helpers import get_fps
from v3xctrl_ui.utils.Settings import Settings
from v3xctrl_ui.osd.WidgetFactory import WidgetFactory
from v3xctrl_ui.osd.WidgetGroupRenderer import WidgetGroupRenderer
from v3xctrl_ui.osd.WidgetGroup import WidgetGroup
from v3xctrl_ui.osd.widgets import Widget


class OSD:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.width = self.settings.get("video").get("width")
        self.height = self.settings.get("video").get("height")

        self.widget_settings = {}
        self.update_settings(settings)

        self.widgets_debug = {}
        self.debug_data: Optional[str] = None
        self.debug_latency: Optional[str] = None
        self.debug_buffer: Optional[str] = None
        self.loop_history: Optional[deque[float]] = None
        self.video_history: Optional[deque[float]] = None
        self._init_widgets_debug()

        self.widgets_signal: Dict[str, Widget] = {}
        self.signal_quality: dict[str, int] = {"rsrq": -1, "rsrp": -1}
        self.signal_band: str = "BAND ?"
        self.signal_cell: str = "CELL ?"
        self._init_widgets_signal()

        self.widgets_battery: Dict[str, Widget] = {}
        self.battery_icon: int = 0
        self.battery_voltage: str = "0.00V"
        self.battery_average_voltage: str = "0.00V"
        self.battery_percent: str = "0%"
        self._init_widgets_battery()

        self.widgets_steering = {}
        self.throttle: float = 0.0
        self.steering: float = 0.0
        self._init_widgets_steering()

        self.reset()

        self.widgets = self.widgets_steering

        # Create unified widget groups for rendering
        self.widget_groups: List[WidgetGroup] = [
            WidgetGroup.create(
                name="steering",
                widgets=self.widgets_steering,
                get_value=lambda name: getattr(self, name),
                use_composition=False
            ),
            WidgetGroup.create(
                name="battery",
                widgets=self.widgets_battery,
                get_value=lambda name: getattr(self, name),
                use_composition=True
            ),
            WidgetGroup.create(
                name="signal",
                widgets=self.widgets_signal,
                get_value=lambda name: getattr(self, name),
                use_composition=True
            ),
            WidgetGroup.create(
                name="debug",
                widgets=self.widgets_debug,
                get_value=lambda name: getattr(self, name),
                use_composition=True
            ),
        ]

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

    def update_buffer_queue(self, size: int) -> None:
        self.widgets_debug["debug_buffer"].set_value(size)

    def update_debug_status(self, status: str) -> None:
        self.debug_data = status

    @property
    def debug_fps_loop(self) -> float:
        return get_fps(self.loop_history)

    @property
    def debug_fps_video(self) -> int:
        if self.video_history is None:
            return 0

        return get_fps(self.video_history)

    def render(
            self,
            screen: pygame.Surface,
            loop_history: deque[float],
            video_history: deque[float] | None
    ) -> None:
        self.loop_history = loop_history
        self.video_history = video_history

        for group in self.widget_groups:
            WidgetGroupRenderer.render_widget_group(
                screen, group, self.widget_settings
            )

    def reset(self) -> None:
        self.debug_data = None
        self.debug_latency = None
        self.debug_buffer = None

        self.widgets_debug["debug_latency"].set_value(None)

        self.signal_quality = {"rsrq": -1, "rsrp": -1}

        self.signal_band = "BAND ?"
        self.signal_cell = "CELL ?"

        self.battery_icon = 0
        self.battery_voltage = "0.00V"
        self.battery_average_voltage = "0.00V"
        self.battery_percent = "0%"
        self.battery_warn = False

        self.throttle = 0.0
        self.steering = 0.0

    def _init_widgets_steering(self) -> None:
        self.widgets_steering = WidgetFactory.create_steering_widgets()

    def _init_widgets_battery(self) -> None:
        self.widgets_battery = WidgetFactory.create_battery_widgets()

    def _init_widgets_signal(self) -> None:
        self.widgets_signal = WidgetFactory.create_signal_widgets()

    def _init_widgets_debug(self) -> None:
        width = self.widget_settings["fps"].get("width")
        height = self.widget_settings["fps"].get("height")
        self.widgets_debug = WidgetFactory.create_debug_widgets(width, height)

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
        data = TelemetryParser.parse(message)

        self.signal_quality = data.signal_quality
        self.signal_band = data.signal_band
        self.signal_cell = data.signal_cell

        self.battery_icon = data.battery_icon
        self.battery_voltage = data.battery_voltage
        self.battery_average_voltage = data.battery_average_voltage
        self.battery_percent = data.battery_percent

        widgets_battery = [
            "battery_voltage",
            "battery_average_voltage",
            "battery_percent"
        ]

        color = RED if data.battery_warning else WHITE
        for widget in widgets_battery:
            self.widgets_battery[widget].set_text_color(color)

        logging.debug(f"Received telemetry message: {message.get_values()}")
