from typing import Dict, Any, List, Tuple

from pygame import Surface

from v3xctrl_ui.utils.fonts import LABEL_FONT
from v3xctrl_ui.utils.i18n import t
from v3xctrl_ui.menu.input import Checkbox
from v3xctrl_ui.core.Settings import Settings

from .Tab import Tab
from .VerticalLayout import VerticalLayout


# (settings_key, label)
CHECKBOX_CONFIG: List[Tuple[str, str]] = [
    ("debug", "Enable Debug Overlay"),
    ("steering", "Show Steering indicator"),
    ("throttle", "Show Throttle indicator"),
    ("battery_icon", "Show Battery Icon"),
    ("battery_voltage", "Show Battery voltage indicator"),
    ("battery_average_voltage", "Show average cell voltage indicator"),
    ("battery_percent", "Show Battery percent indicator"),
    ("signal_quality", "Show Signal quality"),
    ("signal_band", "Show Signal band"),
    ("signal_cell", "Show Signal cell (CAUTION: This potentially exposes your location)"),
    ("rec", "Show Recording indicator"),
    ("clock", "Show Clock (for latency measurement)"),
]


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

        # Create checkboxes from config
        self.checkboxes: Dict[str, Checkbox] = {}
        for key, label in CHECKBOX_CONFIG:
            self.checkboxes[key] = Checkbox(
                label=t(label), font=LABEL_FONT,
                checked=False,
                on_change=lambda value, k=key: self._on_widget_toggle(k, value)
            )

        self.elements = list(self.checkboxes.values())

        self._add_headline("osd", t("OSD"))

        self.osd_layout = VerticalLayout()
        for element in self.elements:
            self.osd_layout.add(element)

        self.apply_settings()

    def draw(self, surface: Surface) -> None:
        _ = self._draw_debug_section(surface, 0)

    def get_settings(self) -> Dict[str, Any]:
        return {
            "widgets": self.widgets
        }

    def apply_settings(self) -> None:
        self.widgets = self.settings.get("widgets", {})

        for key, checkbox in self.checkboxes.items():
            checkbox.checked = self.widgets.get(key, {}).get("display", False)

    def _on_widget_toggle(self, key: str, value: bool) -> None:
        self.widgets.setdefault(key, {})["display"] = value

    def _draw_debug_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        y += self._draw_headline(surface, "osd", y)

        return self.osd_layout.draw(surface, y)
