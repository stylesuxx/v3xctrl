from typing import Dict, Any

from pygame import Surface

from v3xctrl_helper import is_int

from v3xctrl_ui.fonts import LABEL_FONT, MONO_FONT
from v3xctrl_ui.i18n import t
from v3xctrl_ui.menu.input import NumberInput
from v3xctrl_ui.Settings import Settings

from .Tab import Tab


class FrequenciesTab(Tab):
    def __init__(
        self,
        settings: Settings,
        width: int,
        height: int,
        padding: int,
        y_offset: int
    ) -> None:
        super().__init__(settings, width, height, padding, y_offset)

        self.timing = self.settings.get("timing", {})

        label_width = 170
        input_width = 75

        self.video_input = NumberInput(
            t("Main Loop FPS"),
            label_width=label_width,
            input_width=input_width,
            min_val=1, max_val=120,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_rate_change("main_loop_fps", v)
        )

        self.control_input = NumberInput(
            t("Control Frequency"),
            label_width=label_width,
            input_width=input_width,
            min_val=1, max_val=120,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_rate_change("control_update_hz", v)
        )

        self.latency_input = NumberInput(
            t("Latency Frequency"),
            label_width=label_width,
            input_width=input_width,
            min_val=1, max_val=120,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_rate_change("latency_check_hz", v)
        )

        self.video_input.value = str(self.timing.get("main_loop_fps", ""))
        self.control_input.value = str(self.timing.get("control_update_hz", ""))
        self.latency_input.value = str(self.timing.get("latency_check_hz", ""))

        self.elements = [
            self.video_input,
            self.control_input,
            self.latency_input,
        ]

        self.headline_surfaces = {
            "frequencies": self._create_headline(t("Update Frequencies"))
        }

    def draw(self, surface: Surface) -> None:
        _ = self._draw_frequency_section(surface, 0)

    def get_settings(self) -> Dict[str, Any]:
        return {
            "timing": self.timing
        }

    def _on_rate_change(self, name: str, value: str) -> None:
        if is_int(value):
            self.timing[name] = int(value)

    def _draw_frequency_section(self, surface: Surface, y: int) -> int:
        y = self.y_offset + self.padding
        y += self._draw_headline(surface, "frequencies", y)

        self.video_input.set_position(self.padding, y)
        self.video_input.draw(surface)

        y += self.video_input.get_size()[1] + self.y_element_padding
        self.control_input.set_position(self.padding, y)
        self.control_input.draw(surface)

        y += self.control_input.get_size()[1] + self.y_element_padding
        self.latency_input.set_position(self.padding, y)
        self.latency_input.draw(surface)

        return y
