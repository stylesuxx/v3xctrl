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

from v3xctrl_ui.core.TelemetryContext import TelemetryContext

from v3xctrl_ui.core.TelemetryParser import parse_telemetry
from v3xctrl_ui.osd.widgets.WidgetFactory import (
    create_steering_widgets,
    create_battery_widgets,
    create_signal_widgets,
    create_debug_widgets,
    create_rec_widget,
    create_clock_widget,
)
from v3xctrl_ui.osd.widgets.WidgetGroupRenderer import render_widget_group
from v3xctrl_ui.osd.widgets.WidgetGroup import WidgetGroup
from v3xctrl_ui.osd.widgets import Widget

from v3xctrl_ui.utils.colors import ORANGE, RED, WHITE
from v3xctrl_ui.utils.helpers import get_fps
from v3xctrl_ui.core.Settings import Settings


class OSD:
    def __init__(self, settings: Settings, telemetry_context: TelemetryContext) -> None:
        self.settings = settings
        self.telemetry_context = telemetry_context

        self.width = self.settings.get("video").get("width")
        self.height = self.settings.get("video").get("height")

        self.widget_settings = {}
        self.update_settings(settings)

        self.debug_data: Optional[str] = None
        self.debug_latency: Optional[str] = None
        self.debug_buffer: Optional[str] = None
        self.loop_history: Optional[deque[float]] = None
        self.video_history: Optional[deque[float]] = None
        self.is_spectator: bool = False
        self.throttle: float = 0.0
        self.steering: float = 0.0

        self.widgets_debug: Dict[str, Widget] = {}
        self.widgets_signal: Dict[str, Widget] = {}
        self.widgets_battery: Dict[str, Widget] = {}
        self.widgets_rec: Dict[str, Widget] = {}
        self.widgets_steering: Dict[str, Widget] = {}
        self.widgets_clock: Dict[str, Widget] = {}

        self._init_widgets_debug()
        self._init_widgets_signal()
        self._init_widgets_battery()
        self._init_widgets_rec()
        self._init_widgets_steering()
        self._init_widgets_clock()

        self.reset()

        # Create unified widget groups for rendering
        self.widget_groups: List[WidgetGroup] = [
            WidgetGroup.create(
                name="steering",
                widgets=self.widgets_steering,
                get_value=self._get_steering_value,
                use_composition=False
            ),
            WidgetGroup.create(
                name="battery",
                widgets=self.widgets_battery,
                get_value=self._get_battery_value,
                use_composition=True
            ),
            WidgetGroup.create(
                name="signal",
                widgets=self.widgets_signal,
                get_value=self._get_signal_value,
                use_composition=True
            ),
            WidgetGroup.create(
                name="debug",
                widgets=self.widgets_debug,
                get_value=self._get_debug_value,
                use_composition=True
            ),
            WidgetGroup.create(
                name="rec",
                widgets=self.widgets_rec,
                get_value=self._get_rec_value,
                use_composition=False
            ),
            WidgetGroup.create(
                name="clock",
                widgets=self.widgets_clock,
                get_value=self._get_clock_value,
                use_composition=False
            ),
        ]

    @property
    def debug_fps_loop(self) -> float:
        return get_fps(self.loop_history)

    @property
    def debug_fps_video(self) -> int:
        if self.video_history is None:
            return 0

        return get_fps(self.video_history)

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.widget_settings = self.settings.get("widgets", {})

    def set_spectator_mode(self, is_spectator: bool) -> None:
        self.is_spectator = is_spectator

    def message_handler(self, message: Message) -> None:
        match message:
            case Telemetry():
                self._telemetry_update(message)
            case Latency():
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

    def render(
            self,
            screen: pygame.Surface,
            loop_history: deque[float],
            video_history: deque[float] | None
    ) -> None:
        self.loop_history = loop_history
        self.video_history = video_history

        gst = self.telemetry_context.get_gst()

        video_fps_widget = self.widgets_debug["debug_fps_video"]
        if gst.udp_overrun:
            video_fps_widget.set_status_icon("speed", ORANGE)
        else:
            video_fps_widget.clear_status_icon()

        rec_enabled_in_settings = self.widget_settings.get("rec", {}).get("display", True)
        render_settings = {
            **self.widget_settings,
            "rec": {
                **self.widget_settings.get("rec", {}),
                "display": rec_enabled_in_settings and gst.recording
            }
        }

        for group in self.widget_groups:
            render_widget_group(screen, group, render_settings)

    def reset(self) -> None:
        self.debug_data = None
        self.debug_latency = None
        self.debug_buffer = None

        self.widgets_debug["debug_latency"].set_value(None)
        self.telemetry_context.reset()

        self.throttle = 0.0
        self.steering = 0.0

    def _init_widgets_steering(self) -> None:
        self.widgets_steering = create_steering_widgets()

    def _init_widgets_battery(self) -> None:
        self.widgets_battery = create_battery_widgets()

    def _init_widgets_signal(self) -> None:
        self.widgets_signal = create_signal_widgets()

    def _init_widgets_debug(self) -> None:
        width = self.widget_settings["fps"].get("width")
        height = self.widget_settings["fps"].get("height")
        self.widgets_debug = create_debug_widgets(width, height)

    def _init_widgets_rec(self) -> None:
        self.widgets_rec = create_rec_widget()

    def _init_widgets_clock(self) -> None:
        self.widgets_clock = create_clock_widget()

    def _latency_update(self, message: Latency) -> None:
        """
        NOTE: We rely on the streamer and viewer to have the same timezone set
              and do not account for any form of drift.
        """

        # In spectator mode, latency is not meaningful
        if self.is_spectator:
            self.debug_latency = "default"
            self.widgets_debug["debug_latency"].set_value("N/A")

            return

        now = time.time()
        timestamp = message.timestamp
        # RTT/2 for one-way network latency estimate
        diff_ms = round((now - timestamp) * 1000 / 2)

        if diff_ms <= 40:
            self.debug_latency = "green"
        elif diff_ms <= 75:
            self.debug_latency = "yellow"
        else:
            self.debug_latency = "red"

        self.widgets_debug["debug_latency"].set_value(diff_ms)

    def _telemetry_update(self, message: Telemetry) -> None:
        data = parse_telemetry(message)
        values = message.get_values()

        self.telemetry_context.update_signal_quality(
            values["sig"]["rsrq"],
            values["sig"]["rsrp"]
        )
        self.telemetry_context.update_signal_band(data.signal_band)
        self.telemetry_context.update_signal_cell(data.signal_cell)

        self.telemetry_context.update_battery(
            icon=data.battery_icon,
            voltage=data.battery_voltage,
            average_voltage=data.battery_average_voltage,
            percent=data.battery_percent,
            warning=data.battery_warning
        )

        self.telemetry_context.update_services(values.get("svc", 0))
        self.telemetry_context.update_gst(values.get("gst", 0))
        self.telemetry_context.update_videocore(values.get("vc", 0))

        color = RED if data.battery_warning else WHITE
        for widget_name in ["battery_voltage", "battery_average_voltage", "battery_percent"]:
            self.widgets_battery[widget_name].set_text_color(color)

        logging.debug(f"Received telemetry message: {message.get_values()}")

    def _get_steering_value(self, name: str):
        return getattr(self, name)

    def _get_battery_value(self, name: str):
        battery = self.telemetry_context.get_battery()
        mapping = {
            "battery_icon": battery.icon,
            "battery_voltage": battery.voltage,
            "battery_average_voltage": battery.average_voltage,
            "battery_percent": battery.percent,
        }

        return mapping.get(name)

    def _get_signal_value(self, name: str):
        signal = self.telemetry_context.get_signal()
        mapping = {
            "signal_quality": signal.quality,
            "signal_band": signal.band,
            "signal_cell": signal.cell,
        }

        return mapping.get(name)

    def _get_debug_value(self, name: str):
        return getattr(self, name)

    def _get_rec_value(self, name: str):
        gst = self.telemetry_context.get_gst()
        return gst.recording

    def _get_clock_value(self, name: str):
        # ClockWidget gets its own time internally
        return None
