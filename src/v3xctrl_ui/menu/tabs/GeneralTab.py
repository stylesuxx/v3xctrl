from pygame import Surface

from v3xctrl_ui.fonts import LABEL_FONT, MONO_FONT

from v3xctrl_ui.menu.input import Checkbox, NumberInput, TextInput

from .Tab import Tab


class GeneralTab(Tab):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int):
        super().__init__(settings, width, height, padding, y_offset)

        self.ports = self.settings.get("ports", {})
        self.widgets = self.settings.get("widgets", {})
        self.debug = self.settings.get("debug", False)
        self.relay = self.settings.get("relay", {})

        # Port widgets
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
        self.video_input.value = str(self.ports.get("video", ""))
        self.control_input.value = str(self.ports.get("control", ""))

        # Relay server widgets
        self.relay_server_input = TextInput(
            label="Server", label_width=90, input_width=300,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=self._on_relay_server_change
        )
        self.relay_id_input = TextInput(
            label="ID", label_width=90, input_width=300,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=self._on_relay_id_change
        )
        self.relay_enabled_checkbox = Checkbox(
            label="Use UDP Relay", font=LABEL_FONT,
            checked=self.relay.get("enabled", False),
            on_change=self._on_relay_enable_change
        )
        self.relay_server_input.value = self.relay.get("server", "")
        self.relay_id_input.value = self.relay.get("id", "")

        # Miscellanious widgets
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

        self.port_widgets = [
            self.video_input,
            self.control_input
        ]
        self.relay_widgets = [
            self.relay_server_input,
            self.relay_id_input,
            self.relay_enabled_checkbox
        ]
        self.misc_widgets = [
            self.debug_checkbox,
            self.steering_checkbox,
            self.throttle_checkbox
        ]

        self.elements = self.port_widgets + self.relay_widgets + self.misc_widgets

    def _on_port_change(self, name: str, value: str):
        self.ports[name] = int(value)

    def _on_debug_change(self, value: bool):
        self.debug = value

    def _on_steering_change(self, value: bool):
        self.widgets.setdefault("steering", {})["display"] = value

    def _on_throttle_change(self, value: bool):
        self.widgets.setdefault("throttle", {})["display"] = value

    def _on_relay_enable_change(self, value: bool):
        self.relay["enabled"] = value

    def _on_relay_server_change(self, value: str):
        self.relay["server"] = value

    def _on_relay_id_change(self, value: str):
        self.relay["id"] = value

    def _draw_port_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        self._draw_headline(surface, "Ports", y)

        y += self.y_offset_headline
        self.video_input.set_position(self.padding, y)
        self.video_input.draw(surface)

        y += self.video_input.get_size()[1] + self.y_element_padding
        self.control_input.set_position(self.padding, y)
        self.control_input.draw(surface)

        y += self.control_input.get_size()[1] + self.y_note_padding
        note_text = "A restart is required to apply port changes!"
        y = self._draw_note(surface, note_text, y)
        y += self.y_note_padding_bottom

        return y

    def _draw_relay_section(self, surface: Surface, y: int) -> int:
        y += self.y_section_padding
        self._draw_headline(surface, "UDP Relay", y, True)

        y += self.y_offset_headline
        self.relay_server_input.set_position(self.padding, y)
        self.relay_server_input.draw(surface)

        y += self.relay_server_input.get_size()[1] + self.y_element_padding
        self.relay_id_input.set_position(self.padding, y)
        self.relay_id_input.draw(surface)

        y += self.relay_id_input.get_size()[1] + self.y_element_padding
        self.relay_enabled_checkbox.set_position(self.padding, y)
        self.relay_enabled_checkbox.draw(surface)

        y += self.relay_enabled_checkbox.get_size()[1] + self.y_note_padding
        note_text = "A restart is required to apply UDP Relay settings!"
        y = self._draw_note(surface, note_text, y)
        y += self.y_note_padding_bottom

        return y

    def _draw_debug_section(self, surface: Surface, y: int) -> int:
        y += self.y_section_padding
        self._draw_headline(surface, "Miscellaneous", y, True)

        y += self.y_offset_headline
        for checkbox in [self.debug_checkbox, self.steering_checkbox, self.throttle_checkbox]:
            checkbox.set_position(self.padding, y)
            checkbox.draw(surface)
            y += checkbox.get_size()[1] + self.y_element_padding

        return y

    def draw(self, surface: Surface):
        y = self._draw_port_section(surface, 0)
        y = self._draw_relay_section(surface, y)
        y = self._draw_debug_section(surface, y)

    def get_settings(self) -> dict:
        return {
            "debug": self.debug,
            "ports": self.ports,
            "widgets": self.widgets,
            "relay": self.relay
        }
