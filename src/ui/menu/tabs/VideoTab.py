from pygame import event, Surface

from ui.menu.tabs.Tab import Tab
from ui.menu.NumberInput import NumberInput
from ui.fonts import LABEL_FONT, MONO_FONT


class VideoTab(Tab):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int):
        super().__init__(settings, width, height, padding, y_offset)

        self.timing = self.settings.get("timing", {})

        self.label_width = 160
        self.input_width = 75

        self.video_input = NumberInput(
            "Main Loop FPS",
            label_width=self.label_width,
            input_width=self.input_width,
            min_val=1, max_val=120,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_rate_change("main_loop_fps", v)
        )

        self.control_input = NumberInput(
            "Control Frequency",
            label_width=self.label_width,
            input_width=self.input_width,
            min_val=1, max_val=120,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_rate_change("control_update_hz", v)
        )

        self.video_input.set_position(padding, y_offset + padding + 60)
        self.control_input.set_position(padding, y_offset + padding + 100)

        self.video_input.value = str(self.timing.get("main_loop_fps", ""))
        self.control_input.value = str(self.timing.get("control_update_hz", ""))

    def _on_rate_change(self, name: str, value: str):
        self.timing[name] = int(value)

    def handle_event(self, event: event.Event):
        self.video_input.handle_event(event)
        self.control_input.handle_event(event)

    def draw(self, surface: Surface):
        y = self.y_offset + self.padding
        self._draw_headline(surface, "Update Frequencies", y)

        self.video_input.draw(surface)
        self.control_input.draw(surface)

        """
        note_text = "Remember to restart the app after changing the ports!"
        note_surface, note_rect = TEXT_FONT.render(note_text, WHITE)
        note_rect.topleft = (
            self.padding,
            self.control_input.y + self.control_input.input_height + 20
        )
        surface.blit(note_surface, note_rect)

        misc_y = note_rect.bottom + self.padding + 10
        self._draw_headline(surface, "Miscellaneous", misc_y)

        y = misc_y + 60
        for checkbox in [self.debug_checkbox, self.steering_checkbox, self.throttle_checkbox]:
            checkbox.set_position(self.padding, y)
            checkbox.draw(surface)
            y += 40
        """

    def get_settings(self) -> dict:
        return {
            "timing": self.timing
        }
