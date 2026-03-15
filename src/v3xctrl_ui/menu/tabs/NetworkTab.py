from collections.abc import Callable
from typing import Any

import pygame
from pygame import Surface

from v3xctrl_helper import is_int
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.menu.input import BaseInput, BaseWidget, Button, Checkbox, NumberInput, Select, TextInput, WidgetRow
from v3xctrl_ui.utils.colors import GREEN, RED
from v3xctrl_ui.utils.fonts import LABEL_FONT, MONO_FONT, TEXT_FONT
from v3xctrl_ui.utils.i18n import t

from .Tab import Tab
from .VerticalLayout import VerticalLayout


class NetworkTab(Tab):
    def __init__(
        self,
        settings: Settings,
        width: int,
        height: int,
        padding: int,
        y_offset: int,
        on_test_relay: Callable | None = None,
    ) -> None:
        super().__init__(settings, width, height, padding, y_offset)

        self._on_test_relay_callback = on_test_relay
        self._test_status: tuple[bool, str] | None = None

        self._transport_options = ["UDP", "TCP"]

        # Transport select
        self.transport_select = Select(
            label=t("Transport"), label_width=90, length=120, font=LABEL_FONT, callback=self._on_transport_change
        )

        # Port widgets
        self.video_input = NumberInput(
            t("Video"),
            label_width=90,
            input_width=75,
            min_val=1,
            max_val=65535,
            font=LABEL_FONT,
            mono_font=MONO_FONT,
            on_change=lambda value: self._on_port_change("video", value),
        )
        self.control_input = NumberInput(
            t("Control"),
            label_width=90,
            input_width=75,
            min_val=1,
            max_val=65535,
            font=LABEL_FONT,
            mono_font=MONO_FONT,
            on_change=lambda value: self._on_port_change("control", value),
        )

        # Relay server widgets
        self.relay_server_input = TextInput(
            label=t("Server"),
            label_width=90,
            input_width=350,
            font=LABEL_FONT,
            mono_font=MONO_FONT,
            on_change=self._on_relay_server_change,
        )
        self.relay_id_input = TextInput(
            label=t("ID"),
            label_width=90,
            input_width=350,
            font=LABEL_FONT,
            mono_font=MONO_FONT,
            on_change=self._on_relay_id_change,
        )
        self.paste_id_button = Button(
            label=t("Paste ID"), font=LABEL_FONT, callback=self._on_paste_id, height=self.relay_id_input.input_height
        )
        self.test_relay_button = Button(
            label=t("Test"), font=LABEL_FONT, callback=self._on_test_relay, height=self.relay_id_input.input_height
        )
        self.relay_id_row = WidgetRow([self.relay_id_input, self.paste_id_button, self.test_relay_button])

        self.relay_enabled_checkbox = Checkbox(
            label=t("Use UDP Relay"), font=LABEL_FONT, checked=False, on_change=self._on_relay_enable_change
        )
        self.relay_spectator_checkbox = Checkbox(
            label=t("Spectator Mode"), font=LABEL_FONT, checked=False, on_change=self._on_relay_spectator_change
        )

        # Miscellaneous widgets
        self.udp_packet_ttl_input = NumberInput(
            t("UDP packet TTL"),
            label_width=180,
            input_width=75,
            min_val=1,
            max_val=5000,
            font=LABEL_FONT,
            mono_font=MONO_FONT,
            on_change=lambda value: self._on_udp_packet_ttl_change(value),
        )

        self.general_widgets: list[BaseInput | BaseWidget] = [
            self.transport_select,
            self.video_input,
            self.control_input,
        ]
        self.relay_widgets: list[BaseInput | BaseWidget] = [
            self.relay_server_input,
            self.relay_id_row,
            self.relay_enabled_checkbox,
            self.relay_spectator_checkbox,
        ]
        self.control_buffer_capacity_input = NumberInput(
            t("Control Buffer"),
            label_width=180,
            input_width=75,
            min_val=1,
            max_val=100,
            font=LABEL_FONT,
            mono_font=MONO_FONT,
            on_change=lambda value: self._on_control_buffer_capacity_change(value),
        )

        self.misc_widgets: list[BaseInput | BaseWidget] = [
            self.udp_packet_ttl_input,
            self.control_buffer_capacity_input,
        ]

        self.elements = self.general_widgets + self.relay_widgets + self.misc_widgets

        self._add_headline("general", t("General"))
        self._add_headline("udp_relay", t("UDP Relay"), True)
        self._add_headline("misc", t("Miscellaneous"), True)

        self.general_layout = VerticalLayout()
        for element in self.general_widgets:
            self.general_layout.add(element)

        self.relay_layout = VerticalLayout()
        for element in self.relay_widgets:
            self.relay_layout.add(element)

        self.misc_layout = VerticalLayout()
        for element in self.misc_widgets:
            self.misc_layout.add(element)

        self.apply_settings()

    def draw(self, surface: Surface) -> None:
        y = self._draw_general_section(surface, 0)
        y_col1 = self._draw_relay_section(surface, y)

        y = self._draw_misc_section(surface, y_col1)

        self.transport_select.draw_overlay(surface)

    def get_settings(self) -> dict[str, Any]:
        return {
            "udp_packet_ttl": self.udp_packet_ttl,
            "control_buffer_capacity": self.control_buffer_capacity,
            "transport": self.transport,
            "ports": self.ports,
            "relay": self.relay,
        }

    def apply_settings(self) -> None:
        self._test_status = None
        self.transport = self.settings.get("transport", "udp")
        self.ports = self.settings.get("ports", {})
        self.relay = self.settings.get("relay", {})
        self.udp_packet_ttl = self.settings.get("udp_packet_ttl", 100)
        self.control_buffer_capacity = self.settings.get("control_buffer_capacity", 1)

        # Transport select - defer set_options until positioned (rect != None)
        transport_index = (
            self._transport_options.index(self.transport.upper())
            if self.transport.upper() in self._transport_options
            else 0
        )
        self.transport_select.options = self._transport_options
        self.transport_select.selected_index = transport_index

        # Port inputs
        self.video_input.value = str(self.ports.get("video", ""))
        self.control_input.value = str(self.ports.get("control", ""))

        # Relay inputs
        self.relay_server_input.value = self.relay.get("server", "")
        self.relay_id_input.value = self.relay.get("id", "")
        self.relay_enabled_checkbox.checked = self.relay.get("enabled", False)
        self.relay_spectator_checkbox.checked = self.relay.get("spectator_mode", False)

        # Misc inputs
        self.udp_packet_ttl_input.value = str(self.udp_packet_ttl)
        self.control_buffer_capacity_input.value = str(self.control_buffer_capacity)

    def _on_transport_change(self, index: int) -> None:
        self.transport = self._transport_options[index].lower()

    def _on_port_change(self, name: str, value: str) -> None:
        if is_int(value):
            self.ports[name] = int(value)

    def _on_udp_packet_ttl_change(self, value: str) -> None:
        if is_int(value):
            self.udp_packet_ttl = int(value)

    def _on_control_buffer_capacity_change(self, value: str) -> None:
        if is_int(value):
            self.control_buffer_capacity = int(value)

    def _on_relay_enable_change(self, value: bool) -> None:
        self.relay["enabled"] = value

    def _on_relay_server_change(self, value: str) -> None:
        self.relay["server"] = value

    def _on_relay_id_change(self, value: str) -> None:
        self.relay["id"] = value

    def _on_paste_id(self) -> None:
        if pygame.scrap.get_init():
            pasted = self.relay_id_input._get_clipboard_text()
            if pasted:
                self.relay_id_input.value = pasted
                self.relay_id_input.cursor_pos = len(pasted)
                self._on_relay_id_change(pasted)

    def _on_test_relay(self) -> None:
        if not self._on_test_relay_callback:
            return

        server = self.relay_server_input.value
        session_id = self.relay_id_input.value
        spectator_mode = self.relay_spectator_checkbox.checked

        if not server or not session_id:
            self._test_status = (False, t("Server and ID are required"))
            return

        # Parse host:port
        relay_port = 8888
        if ":" in server:
            host, port_str = server.rsplit(":", 1)
            if is_int(port_str):
                relay_port = int(port_str)
                server = host

        self._on_test_relay_callback(server, relay_port, session_id, spectator_mode, self._set_test_status)

    def _set_test_status(self, success: bool, message: str) -> None:
        self._test_status = (success, message)

    def _on_relay_spectator_change(self, value: bool) -> None:
        self.relay["spectator_mode"] = value

    def _draw_general_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        y += self._draw_headline(surface, "general", y)

        return self.general_layout.draw(surface, y)

    def _draw_relay_section(self, surface: Surface, y: int) -> int:
        y += self.y_section_padding
        y += self._draw_headline(surface, "udp_relay", y)

        y = self.relay_layout.draw(surface, y)

        # Draw test status message
        if self._test_status is not None:
            success, message = self._test_status
            color = GREEN if success else RED
            text_surface, text_rect = TEXT_FONT.render(message, color)
            btn = self.test_relay_button
            text_x = btn.x + btn.width + 10
            text_y = btn.y + (btn.height - text_rect.height) // 2
            text_rect.topleft = (text_x, text_y)
            surface.blit(text_surface, text_rect)

        return y

    def _draw_misc_section(self, surface: Surface, y: int) -> int:
        y += self.y_section_padding
        y += self._draw_headline(surface, "misc", y)

        return self.misc_layout.draw(surface, y)
