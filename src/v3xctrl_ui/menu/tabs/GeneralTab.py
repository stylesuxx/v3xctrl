from typing import Dict, List, Any

from pygame import Surface

from v3xctrl_ui.fonts import LABEL_FONT, MONO_FONT
from v3xctrl_ui.menu.input import (
  BaseInput,
  BaseWidget,
  Checkbox,
  NumberInput,
)
from v3xctrl_ui.Settings import Settings

from .Tab import Tab


class GeneralTab(Tab):
    def __init__(
        self,
        settings: Settings,
        width: int,
        height: int,
        padding: int,
        y_offset: int
    ) -> None:
        super().__init__(settings, width, height, padding, y_offset)

        self.video = self.settings.get("video", {})
        self.show_connection_info = self.settings.get("show_connection_info", False)

        # General widgets
        self.fullscreen_enabled_checkbox = Checkbox(
            label="Fullscreen", font=LABEL_FONT,
            checked=self.video.get("fullscreen", False),
            on_change=self._on_fullscreen_enable_change
        )

        self.show_connection_info_checkbox = Checkbox(
            label="Show connection info", font=LABEL_FONT,
            checked=self.show_connection_info,
            on_change=self._on_show_connection_info_change
        )

        self.render_ratio_input = NumberInput(
            "Render Ratio", label_width=120, input_width=75,
            min_val=0, max_val=100,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda value: self._on_render_ratio_change(value)
        )
        self.render_ratio_input.value = str(self.video.get("render_ratio", 0))

        self.general_widgets: List[BaseInput | BaseWidget] = [
            self.fullscreen_enabled_checkbox,
            self.show_connection_info_checkbox,
            self.render_ratio_input
        ]

        self.elements = self.general_widgets

    def draw(self, surface: Surface) -> None:
        _ = self._draw_general_section(surface, 0)

    def get_settings(self) -> Dict[str, Any]:
        return {
            "show_connection_info": self.show_connection_info,
            "video": self.video,
        }

    def _on_render_ratio_change(self, value: str) -> None:
        self.video["render_ratio"] = int(value)

    def _on_show_connection_info_change(self, value: bool) -> None:
        self.show_connection_info = value

    def _on_fullscreen_enable_change(self, value: bool) -> None:
        self.video["fullscreen"] = value

    def _draw_general_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        self._draw_headline(surface, "Settings", y)
        y += self.y_offset_headline

        self.fullscreen_enabled_checkbox.set_position(self.padding, y)
        self.fullscreen_enabled_checkbox.draw(surface)
        y += self.fullscreen_enabled_checkbox.height + self.y_element_padding

        self.show_connection_info_checkbox.set_position(self.padding, y)
        self.show_connection_info_checkbox.draw(surface)
        y += self.show_connection_info_checkbox.height + self.y_element_padding

        self.render_ratio_input.set_position(self.padding, y)
        self.render_ratio_input.draw(surface)
        y += self.render_ratio_input.height + self.y_element_padding

        return y
