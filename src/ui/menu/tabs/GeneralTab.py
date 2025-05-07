from pygame import Surface, event

from ui.menu.tabs.Tab import Tab
from ui.menu.NumberInput import NumberInput
from ui.menu.Checkbox import Checkbox
from ui.colors import WHITE
from ui.fonts import LABEL_FONT, TEXT_FONT, MONO_FONT


class GeneralTab(Tab):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int):
        super().__init__(settings, width, height, padding, y_offset)

        self.ports = self.settings.get("ports", {})
        self.widgets = self.settings.get("widgets", {})
        self.debug = self.settings.get("debug", False)

        self.video_input = NumberInput(
            "Video", label_width=90, input_width=75, min_val=1, max_val=65535,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_port_change("video", v)
        )
        self.control_input = NumberInput(
            "Control", label_width=90, input_width=75, min_val=1, max_val=65535,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda v: self._on_port_change("control", v)
        )
        self.video_input.set_position(padding, y_offset + padding + 60)
        self.control_input.set_position(padding, y_offset + padding + 100)

        self.debug_checkbox = Checkbox(
            label="Enable Debug Overlay", font=LABEL_FONT, checked=self.debug,
            on_change=self._on_debug_change
        )
        self.steering_checkbox = Checkbox(
            label="Enable Steering overlay", font=LABEL_FONT,
            checked=self.widgets.get("steering", {}).get("display", False),
            on_change=self._on_steering_change
        )
        self.throttle_checkbox = Checkbox(
            label="Enable Throttle overlay", font=LABEL_FONT,
            checked=self.widgets.get("throttle", {}).get("display", False),
            on_change=self._on_throttle_change
        )

        self.video_input.value = str(self.ports.get("video", ""))
        self.control_input.value = str(self.ports.get("control", ""))

    def _on_port_change(self, name: str, value: str):
        self.ports[name] = int(value)

    def _on_debug_change(self, value: bool):
        self.debug = value

    def _on_steering_change(self, value: bool):
        self.widgets.setdefault("steering", {})["display"] = value

    def _on_throttle_change(self, value: bool):
        self.widgets.setdefault("throttle", {})["display"] = value

    def handle_event(self, event: event.Event):
        self.video_input.handle_event(event)
        self.control_input.handle_event(event)
        self.debug_checkbox.handle_event(event)
        self.steering_checkbox.handle_event(event)
        self.throttle_checkbox.handle_event(event)

    def draw(self, surface: Surface):
        y = self.y_offset + self.padding
        self._draw_headline(surface, "Ports", y)

        self.video_input.draw(surface)
        self.control_input.draw(surface)

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

    def get_settings(self) -> dict:
        return {
            "debug": self.debug,
            "ports": self.ports,
            "widgets": self.widgets
        }
