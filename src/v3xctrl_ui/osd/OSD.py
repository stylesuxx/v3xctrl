import logging
import time
from collections import deque
from typing import ClassVar

import pygame

from v3xctrl_control.message import Latency, Message, Telemetry
from v3xctrl_helper import SlidingWindowAverage
from v3xctrl_ui.core.dataclasses import BatteryData, GpsData, GpsFixType, SignalData
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.core.TelemetryParser import parse_telemetry
from v3xctrl_ui.osd.widgets import Widget
from v3xctrl_ui.osd.widgets.WidgetFactory import (
    create_battery_widgets,
    create_clock_widget,
    create_debug_widgets,
    create_gps_widgets,
    create_rec_widget,
    create_signal_widgets,
    create_steering_widgets,
)
from v3xctrl_ui.osd.widgets.WidgetGroup import WidgetEntry, WidgetGroup
from v3xctrl_ui.osd.widgets.WidgetGroupRenderer import render_widget_group
from v3xctrl_ui.utils.colors import GREEN, ORANGE, RED, WHITE
from v3xctrl_ui.utils.helpers import get_fps

logger = logging.getLogger(__name__)


class OSD:
    def __init__(self, settings: Settings, telemetry_context: TelemetryContext) -> None:
        self.settings = settings
        self.telemetry_context = telemetry_context

        self.width = settings.video.width
        self.height = settings.video.height

        self.widget_settings = settings.widgets
        self._render_settings = settings.widgets
        self._is_rec_visible: bool | None = None

        self.debug_data: str | None = None
        self.debug_latency: str | None = None
        self.debug_buffer: str | None = None
        self.loop_history: deque[float] | None = None
        self.video_history: deque[float] | None = None
        self.is_spectator: bool = False
        self.throttle: float = 0.0
        self.steering: float = 0.0

        self._latency_samples = SlidingWindowAverage(window_seconds=1.0)

        # Read once at the top of each frame, so every widget in a group shows
        # the same reading and each lock is taken once rather than per widget
        self._frame_battery: BatteryData = telemetry_context.get_battery()
        self._frame_signal: SignalData = telemetry_context.get_signal()
        self._frame_gps: GpsData = telemetry_context.get_gps()

        fps_config = self.widget_settings.fps
        self.widgets_debug: dict[str, Widget] = create_debug_widgets(fps_config.width, fps_config.height)
        self.widgets_signal: dict[str, Widget] = create_signal_widgets()
        self.widgets_battery: dict[str, Widget] = create_battery_widgets()
        self.widgets_rec: dict[str, Widget] = create_rec_widget()
        self.widgets_steering: dict[str, Widget] = create_steering_widgets()
        self.widgets_clock: dict[str, Widget] = create_clock_widget()
        self.widgets_gps: dict[str, Widget] = create_gps_widgets()

        self.reset()

        self.widget_groups: list[WidgetGroup] = self._create_widget_groups()

    @property
    def debug_fps_loop(self) -> float:
        if self.loop_history is None:
            return 0

        return get_fps(self.loop_history)

    @property
    def debug_fps_video(self) -> int:
        if self.video_history is None:
            return 0

        return get_fps(self.video_history)

    def apply_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.widget_settings = settings.widgets

        # Drop the cached REC override so the next frame rebuilds it
        self._render_settings = settings.widgets
        self._is_rec_visible = None

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

    def set_axis_inversion(self, steering: bool, throttle: bool) -> None:
        self.widgets_steering["steering"].inverted = steering
        self.widgets_steering["throttle"].inverted = throttle

    def update_control_queue(self, size: int) -> None:
        self.widgets_debug["debug_data"].set_value(size)

    def update_buffer_queue(self, size: int) -> None:
        self.widgets_debug["debug_buffer"].set_value(size)

    def update_debug_status(self, status: str) -> None:
        self.debug_data = status

    def render(self, screen: pygame.Surface, loop_history: deque[float], video_history: deque[float] | None) -> None:
        self.loop_history = loop_history
        self.video_history = video_history

        gst = self.telemetry_context.get_gst()
        self._frame_battery = self.telemetry_context.get_battery()
        self._frame_signal = self.telemetry_context.get_signal()
        self._frame_gps = self.telemetry_context.get_gps()

        video_fps_widget = self.widgets_debug["debug_fps_video"]
        if gst.udp_overrun:
            video_fps_widget.set_status_icon("speed", ORANGE)
        else:
            video_fps_widget.clear_status_icon()

        # The REC indicator is shown only while recording, so its configured
        # visibility is overridden here. Rebuilt when the recording state flips
        # rather than every frame.
        rec_config = self.widget_settings.get("rec")
        is_rec_visible = (rec_config is None or rec_config.display) and gst.recording

        if is_rec_visible != self._is_rec_visible:
            self._is_rec_visible = is_rec_visible
            self._render_settings = self.widget_settings.with_display("rec", is_rec_visible)

        for group in self.widget_groups:
            render_widget_group(screen, group, self._render_settings)

    def reset(self) -> None:
        self.debug_data = None
        self.debug_latency = None
        self.debug_buffer = None

        self.widgets_debug["debug_latency"].set_value(None)
        self.telemetry_context.reset()
        self.widgets_gps["gps_fix"].set_text_color(WHITE)

        self.throttle = 0.0
        self.steering = 0.0

    def _create_widget_groups(self) -> list[WidgetGroup]:
        """Wire each widget to the one value it draws from."""
        steering = self.widgets_steering
        battery = self.widgets_battery
        signal = self.widgets_signal
        debug = self.widgets_debug
        gps = self.widgets_gps

        return [
            WidgetGroup(
                name="steering",
                entries=(
                    WidgetEntry("steering", steering["steering"], lambda: self.steering),
                    WidgetEntry("throttle", steering["throttle"], lambda: self.throttle),
                ),
                use_composition=False,
            ),
            WidgetGroup(
                name="battery",
                entries=(
                    WidgetEntry("battery_icon", battery["battery_icon"], lambda: self._frame_battery.icon),
                    WidgetEntry("battery_voltage", battery["battery_voltage"], lambda: self._frame_battery.voltage),
                    WidgetEntry(
                        "battery_average_voltage",
                        battery["battery_average_voltage"],
                        lambda: self._frame_battery.average_voltage,
                    ),
                    WidgetEntry("battery_percent", battery["battery_percent"], lambda: self._frame_battery.percent),
                    WidgetEntry("battery_current", battery["battery_current"], lambda: self._frame_battery.current),
                ),
            ),
            WidgetGroup(
                name="signal",
                entries=(
                    WidgetEntry("signal_quality", signal["signal_quality"], lambda: self._frame_signal.quality),
                    WidgetEntry("signal_band", signal["signal_band"], lambda: self._frame_signal.band),
                    WidgetEntry("signal_cell", signal["signal_cell"], lambda: self._frame_signal.cell),
                ),
            ),
            WidgetGroup(
                name="debug",
                entries=(
                    WidgetEntry("debug_fps_loop", debug["debug_fps_loop"], lambda: self.debug_fps_loop),
                    WidgetEntry("debug_fps_video", debug["debug_fps_video"], lambda: self.debug_fps_video),
                    WidgetEntry("debug_data", debug["debug_data"], lambda: self.debug_data),
                    WidgetEntry("debug_latency", debug["debug_latency"], lambda: self.debug_latency),
                    WidgetEntry("debug_buffer", debug["debug_buffer"], lambda: self.debug_buffer),
                ),
            ),
            WidgetGroup(
                name="rec",
                # Whether it is drawn at all is the display override in render()
                entries=(WidgetEntry("rec", self.widgets_rec["rec"], lambda: "REC"),),
                use_composition=False,
            ),
            WidgetGroup(
                name="clock",
                # The clock reads its own time
                entries=(WidgetEntry("clock", self.widgets_clock["clock"], lambda: None),),
                use_composition=False,
            ),
            WidgetGroup(
                name="gps",
                entries=(
                    WidgetEntry("gps_icon", gps["gps_icon"], lambda: self._frame_gps.fix_type),
                    WidgetEntry("gps_fix", gps["gps_fix"], self._gps_fix_label),
                    WidgetEntry("gps_satellites", gps["gps_satellites"], lambda: self._frame_gps.satellites),
                    WidgetEntry("gps_speed", gps["gps_speed"], lambda: self._frame_gps.speed),
                ),
            ),
        ]

    def _gps_fix_label(self) -> str:
        return self._GPS_FIX_LABELS.get(self._frame_gps.fix_type, "NO FIX")

    _GPS_FIX_LABELS: ClassVar[dict[GpsFixType, str]] = {
        GpsFixType.NO_HARDWARE: "NO GPS",
        GpsFixType.NO_FIX: "NO FIX",
        GpsFixType.DEAD_RECKONING: "DEAD REC",
        GpsFixType.FIX_2D: "2D FIX",
        GpsFixType.FIX_3D: "3D FIX",
        GpsFixType.GNSS_DEAD_RECKONING: "GNSS+DR",
    }

    def _latency_update(self, message: Latency) -> None:
        # In spectator mode, latency is not meaningful
        if self.is_spectator:
            self.debug_latency = "default"
            self.widgets_debug["debug_latency"].set_value("N/A")

            return

        # RTT/2 for one-way network latency estimate
        diff_ms = (time.time() - message.timestamp) * 1000 / 2
        self._latency_samples.append(diff_ms)

        avg_ms = round(self._latency_samples.average)

        if avg_ms <= 40:
            self.debug_latency = "green"
        elif avg_ms <= 75:
            self.debug_latency = "yellow"
        else:
            self.debug_latency = "red"

        self.widgets_debug["debug_latency"].set_value(avg_ms)

    def _telemetry_update(self, message: Telemetry) -> None:
        data = parse_telemetry(message)
        values = message.get_values()

        self.telemetry_context.update_signal_quality(values["sig"]["rsrq"], values["sig"]["rsrp"])
        self.telemetry_context.update_signal_band(data.signal_band)
        self.telemetry_context.update_signal_cell(data.signal_cell)

        self.telemetry_context.update_battery(
            icon=data.battery_icon,
            voltage=data.battery_voltage,
            average_voltage=data.battery_average_voltage,
            percent=data.battery_percent,
            current=data.battery_current,
            warning=data.battery_warning,
        )

        self.telemetry_context.update_gps(
            fix_type=data.gps_fix_type,
            speed=data.gps_speed,
            satellites=data.gps_satellites,
        )
        self.telemetry_context.update_services(values.get("svc", 0))
        self.telemetry_context.update_gst(values.get("gst", 0))
        self.telemetry_context.update_videocore(values.get("vc", 0))

        color = RED if data.battery_warning else WHITE
        for widget_name in ["battery_voltage", "battery_average_voltage", "battery_percent", "battery_current"]:
            if widget_name in self.widgets_battery:
                self.widgets_battery[widget_name].set_text_color(color)

        fix_color = RED
        if data.gps_fix_type == GpsFixType.NO_HARDWARE:
            fix_color = WHITE
        elif data.gps_fix_type >= GpsFixType.FIX_3D:
            fix_color = GREEN
        elif data.gps_fix_type >= GpsFixType.DEAD_RECKONING:
            fix_color = ORANGE

        self.widgets_gps["gps_fix"].set_text_color(fix_color)
