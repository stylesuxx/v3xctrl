"""Factory for creating OSD widget groups."""
from typing import Dict
from v3xctrl_ui.utils.fonts import BOLD_MONO_FONT_14
from v3xctrl_ui.utils.helpers import (
    interpolate_steering_color,
    interpolate_throttle_color,
)
from v3xctrl_ui.osd.widgets import (
    Widget,
    BatteryIconWidget,
    Alignment,
    FpsWidget,
    HorizontalIndicatorWidget,
    StatusValueWidget,
    SignalQualityWidget,
    TextWidget,
    VerticalIndicatorWidget,
)


class WidgetFactory:
    @staticmethod
    def create_steering_widgets() -> Dict[str, Widget]:
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

        return {
            "steering": steering_widget,
            "throttle": throttle_widget
        }

    @staticmethod
    def create_battery_widgets() -> Dict[str, Widget]:
        position = (0, 0)

        battery_voltage_widget = TextWidget(position, 70)
        battery_average_voltage_widget = TextWidget(position, 70)
        battery_percent_widget = TextWidget(position, 70)

        battery_voltage_widget.set_alignment(Alignment.RIGHT)
        battery_average_voltage_widget.set_alignment(Alignment.RIGHT)
        battery_percent_widget.set_alignment(Alignment.RIGHT)

        battery_icon_widget = BatteryIconWidget(position, 70)

        return {
            "battery_icon": battery_icon_widget,
            "battery_voltage": battery_voltage_widget,
            "battery_average_voltage": battery_average_voltage_widget,
            "battery_percent": battery_percent_widget
        }

    @staticmethod
    def create_signal_widgets() -> Dict[str, Widget]:
        position = (0, 0)

        signal_quality_widget = SignalQualityWidget(position, (70, 50))
        signal_band_widget = TextWidget(position, 70)
        signal_cell_widget = TextWidget(position, 70)
        signal_cell_widget.font = BOLD_MONO_FONT_14

        return {
            "signal_quality": signal_quality_widget,
            "signal_band": signal_band_widget,
            "signal_cell": signal_cell_widget
        }

    @staticmethod
    def create_debug_widgets(fps_width: int, fps_height: int) -> Dict[str, Widget]:
        position = (0, 0)

        debug_fps_loop_widget = FpsWidget(position, (fps_width, fps_height), "LOOP")
        debug_fps_video_widget = FpsWidget(position, (fps_width, fps_height), "VIDEO")
        debug_data_widget = StatusValueWidget(position, 26, "DATA", average=True)
        debug_latency_widget = StatusValueWidget(position, 26, "LATENCY")
        debug_buffer_widget = StatusValueWidget(position, 26, "BUFFER", average=True, average_window=2)

        return {
            "debug_fps_loop": debug_fps_loop_widget,
            "debug_fps_video": debug_fps_video_widget,
            "debug_data": debug_data_widget,
            "debug_latency": debug_latency_widget,
            "debug_buffer": debug_buffer_widget
        }
