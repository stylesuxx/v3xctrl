from typing import Dict, List, Any

from pygame import Surface

from v3xctrl_ui.fonts import LABEL_FONT, MONO_FONT
from v3xctrl_ui.menu.input import (
  BaseInput,
  BaseWidget,
  Checkbox,
  NumberInput,
  TextInput
)
from v3xctrl_ui.Settings import Settings
from v3xctrl_helper import is_int

from .Tab import Tab


class NetworkTab(Tab):
    def __init__(
        self,
        settings: Settings,
        width: int,
        height: int,
        padding: int,
        y_offset: int
    ) -> None:
        super().__init__(settings, width, height, padding, y_offset)

        self.ports = self.settings.get("ports", {})
        self.relay = self.settings.get("relay", {})
        self.udp_packet_ttl = self.settings.get("udp_packet_ttl", 100)

        # Port widgets
        self.video_input = NumberInput(
            "Video", label_width=90, input_width=75, min_val=1, max_val=65535,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda value: self._on_port_change("video", value)
        )
        self.control_input = NumberInput(
            "Control", label_width=90, input_width=75, min_val=1, max_val=65535,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda value: self._on_port_change("control", value)
        )
        self.video_input.value = str(self.ports.get("video", ""))
        self.control_input.value = str(self.ports.get("control", ""))

        # Relay server widgets
        self.relay_server_input = TextInput(
            label="Server", label_width=90, input_width=350,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=self._on_relay_server_change
        )
        self.relay_id_input = TextInput(
            label="ID", label_width=90, input_width=350,
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
        self.udp_packet_ttl_input = NumberInput(
            "UDP packet TTL", label_width=180, input_width=75, min_val=1, max_val=5000,
            font=LABEL_FONT, mono_font=MONO_FONT,
            on_change=lambda value: self._on_udp_packet_ttl_change(value)
        )
        self.udp_packet_ttl_input.value = str(self.udp_packet_ttl)

        self.port_widgets: List[BaseInput] = [
            self.video_input,
            self.control_input
        ]
        self.relay_widgets: List[BaseInput | BaseWidget] = [
            self.relay_server_input,
            self.relay_id_input,
            self.relay_enabled_checkbox
        ]
        self.misc_widgets: List[BaseInput | BaseWidget] = [
            self.udp_packet_ttl_input
        ]

        self.elements = self.port_widgets + self.relay_widgets + self.misc_widgets

        self.headline_surfaces = {
            "ports": self._create_headline("Ports"),
            "udp_relay": self._create_headline("UDP Relay", True),
            "misc": self._create_headline("Miscellaneous", True),
        }

    def draw(self, surface: Surface) -> None:
        y = self._draw_port_section(surface, 0)
        y_col1 = self._draw_relay_section(surface, y)

        y = self._draw_misc_section(surface, y_col1)

    def get_settings(self) -> Dict[str, Any]:
        return {
            "udp_packet_ttl": self.udp_packet_ttl,
            "ports": self.ports,
            "relay": self.relay,
        }

    def _on_port_change(self, name: str, value: str) -> None:
        if is_int(value):
            self.ports[name] = int(value)

    def _on_udp_packet_ttl_change(self, value: str) -> None:
        if is_int(value):
            self.udp_packet_ttl = int(value)

    def _on_relay_enable_change(self, value: bool) -> None:
        self.relay["enabled"] = value

    def _on_relay_server_change(self, value: str) -> None:
        self.relay["server"] = value

    def _on_relay_id_change(self, value: str) -> None:
        self.relay["id"] = value

    def _draw_port_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding

        self._draw_headline(surface, "Ports", y)
        y += self.y_offset_headline

        self.video_input.set_position(self.padding, y)
        self.video_input.draw(surface)
        y += self.video_input.height + self.y_element_padding

        self.control_input.set_position(self.padding, y)
        self.control_input.draw(surface)
        y += self.control_input.height + self.y_element_padding

        return y

    def _draw_relay_section(self, surface: Surface, y: int) -> int:
        y += self.y_section_padding
        self._draw_headline(surface, "UDP Relay", y, True)
        y += self.y_offset_headline

        self.relay_server_input.set_position(self.padding, y)
        self.relay_server_input.draw(surface)
        y += self.relay_server_input.height + self.y_element_padding

        self.relay_id_input.set_position(self.padding, y)
        self.relay_id_input.draw(surface)
        y += self.relay_id_input.height + self.y_element_padding

        self.relay_enabled_checkbox.set_position(self.padding, y)
        self.relay_enabled_checkbox.draw(surface)
        y += self.relay_enabled_checkbox.height + self.y_element_padding

        return y

    def _draw_misc_section(self, surface: Surface, y: int) -> int:
        y += self.y_section_padding
        self._draw_headline(surface, "Miscellaneous", y, True)
        y += self.y_offset_headline

        self.udp_packet_ttl_input.set_position(self.padding, y)
        self.udp_packet_ttl_input.draw(surface)
        y += self.udp_packet_ttl_input.height + self.y_element_padding

        return y
