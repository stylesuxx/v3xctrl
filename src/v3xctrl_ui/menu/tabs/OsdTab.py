from typing import Any

from pygame import Surface

from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.menu.input import Checkbox
from v3xctrl_ui.utils.fonts import LABEL_FONT
from v3xctrl_ui.utils.i18n import t

from .Tab import Tab
from .VerticalLayout import VerticalLayout

# (settings_key, label)
CHECKBOX_CONFIG: list[tuple[str, str]] = [
    ("debug", "Enable Debug Overlay"),
    ("steering", "Show Steering indicator"),
    ("throttle", "Show Throttle indicator"),
    ("battery_icon", "Show Battery Icon"),
    ("battery_voltage", "Show Battery voltage indicator"),
    ("battery_average_voltage", "Show average cell voltage indicator"),
    ("battery_percent", "Show Battery percent indicator"),
    ("battery_current", "Show Battery current"),
    ("signal_quality", "Show Signal quality"),
    ("signal_band", "Show Signal band"),
    ("signal_cell", "Show Signal cell (CAUTION: This potentially exposes your location)"),
    ("rec", "Show Recording indicator"),
    ("clock", "Show Clock (for latency measurement)"),
    ("gps_icon", "Show GPS Icon"),
    ("gps_fix", "Show GPS Fix Status"),
    ("gps_satellites", "Show GPS Satellite Count"),
    ("gps_speed", "Show GPS Speed"),
]


class OsdTab(Tab):
    def __init__(self, settings: Settings, width: int, height: int, padding: int, y_offset: int) -> None:
        super().__init__(settings, width, height, padding, y_offset)

        self.checkboxes: dict[str, Checkbox] = {}
        self._add_headline("osd", t("OSD"))

        self.column_left = VerticalLayout()
        self.column_right = VerticalLayout(padding_x=self.width // 2)

        for key, label in CHECKBOX_CONFIG:
            checkbox = Checkbox(
                label=t(label),
                font=LABEL_FONT,
                checked=False,
                on_change=lambda value, k=key: self._on_widget_toggle(k, value),
            )
            self.checkboxes[key] = checkbox

            if key.startswith("gps_"):
                self.column_right.add(checkbox)
            else:
                self.column_left.add(checkbox)

        self.apply_settings()

    def draw(self, surface: Surface) -> None:
        _ = self._draw_debug_section(surface, 0)

    def get_settings(self) -> dict[str, Any]:
        return {"widgets": self.widgets}

    def apply_settings(self) -> None:
        self.widgets = self.settings.get("widgets", {})

        for key, checkbox in self.checkboxes.items():
            checkbox.checked = self.widgets.get(key, {}).get("display", False)

    def _on_widget_toggle(self, key: str, value: bool) -> None:
        self.widgets.setdefault(key, {})["display"] = value

    def _draw_debug_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        y += self._draw_headline(surface, "osd", y)

        y_start = y
        left_end = self.column_left.draw(surface, y_start)
        right_end = self.column_right.draw(surface, y_start)

        return max(left_end, right_end)
