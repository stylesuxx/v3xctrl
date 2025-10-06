from typing import Dict, Any

from pygame import Surface

from v3xctrl_ui.fonts import LABEL_FONT
from v3xctrl_ui.menu.input import Checkbox
from v3xctrl_ui.Settings import Settings

from .Tab import Tab


class OsdTab(Tab):
    def __init__(
        self,
        settings: Settings,
        width: int,
        height: int,
        padding: int,
        y_offset: int
    ) -> None:
        super().__init__(settings, width, height, padding, y_offset)

        self.widgets = self.settings.get("widgets", {})

        # OSD widgets
        self.debug_checkbox = Checkbox(
            label="Enable Debug Overlay", font=LABEL_FONT,
            checked=self.widgets.get("debug", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("debug", value)
        )
        self.steering_checkbox = Checkbox(
            label="Show Steering indicator", font=LABEL_FONT,
            checked=self.widgets.get("steering", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("steering", value)
        )
        self.throttle_checkbox = Checkbox(
            label="Show Throttle indicator", font=LABEL_FONT,
            checked=self.widgets.get("throttle", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("throttle", value)
        )
        self.battery_icon_checkbox = Checkbox(
            label="Show Battery Icon", font=LABEL_FONT,
            checked=self.widgets.get("battery_icon", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("battery_icon", value)
        )
        self.battery_voltage_checkbox = Checkbox(
            label="Show Battery voltage indicator", font=LABEL_FONT,
            checked=self.widgets.get("battery_voltage", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("battery_voltage", value)
        )
        self.battery_average_voltage_checkbox = Checkbox(
            label="Show average cell voltage indicator", font=LABEL_FONT,
            checked=self.widgets.get("battery_average_voltage", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("battery_average_voltage", value)
        )
        self.battery_percent_checkbox = Checkbox(
            label="Show Battery percent indicator", font=LABEL_FONT,
            checked=self.widgets.get("battery_percent", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("battery_percent", value)
        )
        self.signal_checkbox = Checkbox(
            label="Show Signal indicator", font=LABEL_FONT,
            checked=self.widgets.get("signal", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("signal", value)
        )

        self.osd_widgets = [
            self.debug_checkbox,
            self.steering_checkbox,
            self.throttle_checkbox,
            self.battery_icon_checkbox,
            self.battery_voltage_checkbox,
            self.battery_average_voltage_checkbox,
            self.battery_percent_checkbox,
            self.signal_checkbox
        ]

        self.elements = self.osd_widgets

    def draw(self, surface: Surface) -> None:
        _ = self._draw_debug_section(surface, 0)

    def get_settings(self) -> Dict[str, Any]:
        return {
            "widgets": self.widgets
        }

    def _on_widget_toggle(self, key: str, value: bool) -> None:
        self.widgets.setdefault(key, {})["display"] = value

    def _draw_debug_section(self, surface: Surface, y: int) -> int:
        y = self.y_offset + self.padding
        self._draw_headline(surface, "OSD", y)

        y += self.y_offset_headline
        for checkbox in self.osd_widgets:
            checkbox.set_position(self.padding, y)
            checkbox.draw(surface)
            y += checkbox.get_size()[1] + self.y_element_padding

        return y
