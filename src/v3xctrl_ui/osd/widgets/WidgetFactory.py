from dataclasses import dataclass

from v3xctrl_ui.osd.widgets.BatteryIconWidget import BatteryIconWidget
from v3xctrl_ui.osd.widgets.ClockWidget import ClockWidget
from v3xctrl_ui.osd.widgets.FpsWidget import FpsWidget
from v3xctrl_ui.osd.widgets.GpsIconWidget import GpsIconWidget
from v3xctrl_ui.osd.widgets.GpsSpeedWidget import GpsSpeedWidget
from v3xctrl_ui.osd.widgets.HorizontalIndicatorWidget import HorizontalIndicatorWidget
from v3xctrl_ui.osd.widgets.RecWidget import RecWidget
from v3xctrl_ui.osd.widgets.SignalQualityWidget import SignalQualityWidget
from v3xctrl_ui.osd.widgets.StatusValueWidget import StatusValueWidget
from v3xctrl_ui.osd.widgets.TextWidget import Alignment, TextWidget
from v3xctrl_ui.osd.widgets.VerticalIndicatorWidget import VerticalIndicatorWidget
from v3xctrl_ui.utils.fonts import BOLD_MONO_FONT_14
from v3xctrl_ui.utils.helpers import (
    interpolate_steering_color,
    interpolate_throttle_color,
)


@dataclass(frozen=True, slots=True)
class SteeringWidgets:
    steering: HorizontalIndicatorWidget
    throttle: VerticalIndicatorWidget


@dataclass(frozen=True, slots=True)
class BatteryWidgets:
    icon: BatteryIconWidget
    voltage: TextWidget
    average_voltage: TextWidget
    percent: TextWidget
    current: TextWidget


@dataclass(frozen=True, slots=True)
class SignalWidgets:
    quality: SignalQualityWidget
    band: TextWidget
    cell: TextWidget


@dataclass(frozen=True, slots=True)
class DebugWidgets:
    fps_loop: FpsWidget
    fps_video: FpsWidget
    data: StatusValueWidget
    latency: StatusValueWidget
    buffer: StatusValueWidget


@dataclass(frozen=True, slots=True)
class GpsWidgets:
    icon: GpsIconWidget
    fix: TextWidget
    satellites: TextWidget
    speed: GpsSpeedWidget


def create_steering_widgets() -> SteeringWidgets:
    steering_widget = HorizontalIndicatorWidget(
        position=(0, 0), size=(412, 22), bar_size=(20, 10), range_mode="symmetric", color_fn=interpolate_steering_color
    )

    throttle_widget = VerticalIndicatorWidget(
        position=(0, 0), size=(32, 212), bar_width=20, range_mode="symmetric", color_fn=interpolate_throttle_color
    )

    return SteeringWidgets(steering=steering_widget, throttle=throttle_widget)


def create_battery_widgets() -> BatteryWidgets:
    position = (0, 0)

    battery_voltage_widget = TextWidget(position, 70)
    battery_average_voltage_widget = TextWidget(position, 70)
    battery_percent_widget = TextWidget(position, 70)
    battery_current_widget = TextWidget(position, 70)

    battery_voltage_widget.set_alignment(Alignment.RIGHT)
    battery_average_voltage_widget.set_alignment(Alignment.RIGHT)
    battery_percent_widget.set_alignment(Alignment.RIGHT)
    battery_current_widget.set_alignment(Alignment.RIGHT)

    battery_icon_widget = BatteryIconWidget(position, 70)

    return BatteryWidgets(
        icon=battery_icon_widget,
        voltage=battery_voltage_widget,
        average_voltage=battery_average_voltage_widget,
        percent=battery_percent_widget,
        current=battery_current_widget,
    )


def create_signal_widgets() -> SignalWidgets:
    position = (0, 0)

    signal_quality_widget = SignalQualityWidget(position, (70, 50))
    signal_band_widget = TextWidget(position, 70)
    signal_cell_widget = TextWidget(position, 70)
    signal_cell_widget.font = BOLD_MONO_FONT_14

    return SignalWidgets(quality=signal_quality_widget, band=signal_band_widget, cell=signal_cell_widget)


def create_debug_widgets(fps_width: int, fps_height: int) -> DebugWidgets:
    position = (0, 0)

    return DebugWidgets(
        fps_loop=FpsWidget(position, (fps_width, fps_height), "LOOP"),
        fps_video=FpsWidget(position, (fps_width, fps_height), "VIDEO"),
        data=StatusValueWidget(position, 26, "CTRL", average=True),
        latency=StatusValueWidget(position, 26, "LATENCY"),
        buffer=StatusValueWidget(position, 26, "BUFFER", average=True, average_window=2),
    )


def create_rec_widget() -> RecWidget:
    return RecWidget((0, 0))


def create_clock_widget() -> ClockWidget:
    return ClockWidget((0, 0))


def create_gps_widgets() -> GpsWidgets:
    position = (0, 0)

    gps_icon_widget = GpsIconWidget(position, 70)
    gps_fix_widget = TextWidget(position, 70)
    gps_satellites_widget = TextWidget(position, 70)
    gps_speed_widget = GpsSpeedWidget(position, 70)

    gps_fix_widget.set_alignment(Alignment.RIGHT)
    gps_satellites_widget.set_alignment(Alignment.RIGHT)

    return GpsWidgets(
        icon=gps_icon_widget,
        fix=gps_fix_widget,
        satellites=gps_satellites_widget,
        speed=gps_speed_widget,
    )
