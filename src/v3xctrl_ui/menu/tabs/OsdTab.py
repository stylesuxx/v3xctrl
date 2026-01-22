from typing import Dict, Any

from pygame import Surface

from v3xctrl_ui.utils.fonts import LABEL_FONT
from v3xctrl_ui.utils.i18n import t
from v3xctrl_ui.menu.input import Checkbox
from v3xctrl_ui.core.Settings import Settings

from .Tab import Tab
from .VerticalLayout import VerticalLayout


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
            label=t("Enable Debug Overlay"), font=LABEL_FONT,
            checked=self.widgets.get("debug", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("debug", value)
        )
        self.steering_checkbox = Checkbox(
            label=t("Show Steering indicator"), font=LABEL_FONT,
            checked=self.widgets.get("steering", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("steering", value)
        )
        self.throttle_checkbox = Checkbox(
            label=t("Show Throttle indicator"), font=LABEL_FONT,
            checked=self.widgets.get("throttle", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("throttle", value)
        )
        self.battery_icon_checkbox = Checkbox(
            label=t("Show Battery Icon"), font=LABEL_FONT,
            checked=self.widgets.get("battery_icon", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("battery_icon", value)
        )
        self.battery_voltage_checkbox = Checkbox(
            label=t("Show Battery voltage indicator"), font=LABEL_FONT,
            checked=self.widgets.get("battery_voltage", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("battery_voltage", value)
        )
        self.battery_average_voltage_checkbox = Checkbox(
            label=t("Show average cell voltage indicator"), font=LABEL_FONT,
            checked=self.widgets.get("battery_average_voltage", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("battery_average_voltage", value)
        )
        self.battery_percent_checkbox = Checkbox(
            label=t("Show Battery percent indicator"), font=LABEL_FONT,
            checked=self.widgets.get("battery_percent", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("battery_percent", value)
        )
        self.signal_quality_checkbox = Checkbox(
            label=t("Show Signal quality"), font=LABEL_FONT,
            checked=self.widgets.get("signal_quality", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("signal_quality", value)
        )
        self.signal_band_checkbox = Checkbox(
            label=t("Show Signal band"), font=LABEL_FONT,
            checked=self.widgets.get("signal_band", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("signal_band", value)
        )
        self.signal_cell_checkbox = Checkbox(
            label=t("Show Signal cell (CAUTION: This potentially exposes your location)"), font=LABEL_FONT,
            checked=self.widgets.get("signal_cell", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("signal_cell", value)
        )
        self.rec_checkbox = Checkbox(
            label=t("Show Recording indicator"), font=LABEL_FONT,
            checked=self.widgets.get("rec", {}).get("display", False),
            on_change=lambda value: self._on_widget_toggle("rec", value)
        )

        self.osd_widgets = [
            self.debug_checkbox,
            self.steering_checkbox,
            self.throttle_checkbox,
            self.battery_icon_checkbox,
            self.battery_voltage_checkbox,
            self.battery_average_voltage_checkbox,
            self.battery_percent_checkbox,
            self.signal_quality_checkbox,
            self.signal_band_checkbox,
            self.signal_cell_checkbox,
            self.rec_checkbox,
        ]

        self.elements = self.osd_widgets

        self._add_headline("osd", t("OSD"))

        self.osd_layout = VerticalLayout()
        for element in self.osd_widgets:
            self.osd_layout.add(element)

    def draw(self, surface: Surface) -> None:
        _ = self._draw_debug_section(surface, 0)

    def get_settings(self) -> Dict[str, Any]:
        return {
            "widgets": self.widgets
        }

    def _on_widget_toggle(self, key: str, value: bool) -> None:
        self.widgets.setdefault(key, {})["display"] = value

    def _draw_debug_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        y += self._draw_headline(surface, "osd", y)

        return self.osd_layout.draw(surface, y)
