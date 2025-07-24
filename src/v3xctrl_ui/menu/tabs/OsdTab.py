from pygame import Surface

from v3xctrl_ui.fonts import LABEL_FONT
from v3xctrl_ui.menu.input import Checkbox

from .Tab import Tab


class OsdTab(Tab):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int):
        super().__init__(settings, width, height, padding, y_offset)

        self.debug = self.settings.get("debug", False)
        self.widgets = self.settings.get("widgets", {})

        # OSD widgets
        self.debug_checkbox = Checkbox(
            label="Enable Debug Overlay", font=LABEL_FONT, checked=self.debug,
            on_change=self._on_debug_change
        )
        self.steering_checkbox = Checkbox(
            label="Show Steering indicator", font=LABEL_FONT,
            checked=self.widgets.get("steering", {}).get("display", False),
            on_change=self._on_steering_change
        )
        self.throttle_checkbox = Checkbox(
            label="Show Throttle indicator", font=LABEL_FONT,
            checked=self.widgets.get("throttle", {}).get("display", False),
            on_change=self._on_throttle_change
        )

        self.osd_widgets = [
            self.debug_checkbox,
            self.steering_checkbox,
            self.throttle_checkbox
        ]

        self.elements = self.osd_widgets

    def _on_debug_change(self, value: bool) -> None:
        self.debug = value

    def _on_steering_change(self, value: bool) -> None:
        self.widgets.setdefault("steering", {})["display"] = value

    def _on_throttle_change(self, value: bool) -> None:
        self.widgets.setdefault("throttle", {})["display"] = value

    def _draw_debug_section(self, surface: Surface, y: int) -> int:
        y = self.y_offset + self.padding
        self._draw_headline(surface, "OSD", y)

        y += self.y_offset_headline
        for checkbox in self.osd_widgets:
            checkbox.set_position(self.padding, y)
            checkbox.draw(surface)
            y += checkbox.get_size()[1] + self.y_element_padding

        return y

    def draw(self, surface: Surface) -> None:
        _ = self._draw_debug_section(surface, 0)

    def get_settings(self) -> dict:
        return {
            "debug": self.debug,
            "widgets": self.widgets
        }
