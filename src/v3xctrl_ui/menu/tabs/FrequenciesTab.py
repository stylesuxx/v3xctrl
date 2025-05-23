from pygame import event, Surface

from v3xctrl_ui.fonts import LABEL_FONT, MONO_FONT
from v3xctrl_ui.menu.input import NumberInput

from .Tab import Tab


class FrequenciesTab(Tab):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int):
        super().__init__(settings, width, height, padding, y_offset)

        self.timing = self.settings.get("timing", {})

        label_width = 170
        input_width = 75
        element_padding = 10

        self.video_input = NumberInput(
            "Main Loop FPS",
            label_width=label_width,
            input_width=input_width,
            min_val=1, max_val=120,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_rate_change("main_loop_fps", v)
        )

        self.control_input = NumberInput(
            "Control Frequency",
            label_width=label_width,
            input_width=input_width,
            min_val=1, max_val=120,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_rate_change("control_update_hz", v)
        )

        self.latency_input = NumberInput(
            "Latency Frequency",
            label_width=label_width,
            input_width=input_width,
            min_val=1, max_val=120,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_rate_change("latency_check_hz", v)
        )

        y_position = y_offset + padding + 60

        self.video_input.set_position(padding, y_position)
        width, height = self.video_input.get_size()
        y_position += height + element_padding

        self.control_input.set_position(padding, y_position)
        width, height = self.control_input.get_size()
        y_position += height + element_padding

        self.latency_input.set_position(padding, y_position)

        self.video_input.value = str(self.timing.get("main_loop_fps", ""))
        self.control_input.value = str(self.timing.get("control_update_hz", ""))
        self.latency_input.value = str(self.timing.get("latency_check_hz", ""))

    def _on_rate_change(self, name: str, value: str):
        self.timing[name] = int(value)

    def handle_event(self, event: event.Event):
        self.video_input.handle_event(event)
        self.control_input.handle_event(event)
        self.latency_input.handle_event(event)

    def draw(self, surface: Surface):
        y = self.y_offset + self.padding
        self._draw_headline(surface, "Update Frequencies", y)

        self.video_input.draw(surface)
        self.control_input.draw(surface)
        self.latency_input.draw(surface)

    def get_settings(self) -> dict:
        return {
            "timing": self.timing
        }
