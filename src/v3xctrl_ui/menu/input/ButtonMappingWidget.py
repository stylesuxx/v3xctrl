from typing import Any
from collections.abc import Callable

import pygame
from pygame import Surface
from pygame.freetype import Font

from v3xctrl_ui.menu.input import Button, BaseWidget
from v3xctrl_ui.utils.colors import WHITE

# Mapping value is either an int (button index) or a dict (hat mapping)
MappingValue = int | dict[str, Any] | None

HAT_DIRECTION_NAMES: dict[tuple[int, int], str] = {
    (0, 1): "Up",
    (0, -1): "Down",
    (-1, 0): "Left",
    (1, 0): "Right",
    (1, 1): "Up-Right",
    (-1, 1): "Up-Left",
    (1, -1): "Down-Right",
    (-1, -1): "Down-Left",
}


def format_mapping(mapping: MappingValue) -> str:
    if mapping is None:
        return "N/A"
    if isinstance(mapping, int):
        return f"Button {mapping}"
    if isinstance(mapping, dict) and "hat" in mapping:
        value = tuple(mapping["value"])
        direction = HAT_DIRECTION_NAMES.get(value, str(value))
        return f"Hat {mapping['hat']} {direction}"
    return "N/A"


class ButtonMappingWidget(BaseWidget):
    FONT_COLOR = WHITE
    BUTTON_TEXT_OFFSET_X = 140
    REMAP_BUTTON_OFFSET_X = 280
    PADDING = 10
    WIDTH = 260
    BAR_HEIGHT = 30  # Match GamepadCalibrationWidget.BAR_HEIGHT for alignment

    @property
    def hover_children(self) -> list[BaseWidget]:
        return [self.remap_button, self.reset_button]

    def __init__(
        self,
        control_name: str,
        button_number: MappingValue,
        font: Font,
        on_button_change: Callable[[MappingValue], None],
        on_remap_toggle: Callable[[bool], None]
    ) -> None:
        super().__init__()

        self.control_name = control_name
        self.button_number = button_number
        self.font = font
        self.on_button_change = on_button_change
        self.on_remap_toggle = on_remap_toggle

        self.waiting_for_button = False

        btn_w = int(font.size * 4)
        self.remap_button = Button("Assign", font, self._on_remap_click, width=btn_w)
        self.reset_button = Button("Reset", font, self._on_reset_click, width=btn_w)

        # Disable reset button if no button is mapped
        if button_number is None:
            self.reset_button.disable()

        self._render_label()

    def handle_event(self, event: pygame.event.Event) -> bool:
        self.remap_button.handle_event(event)
        self.reset_button.handle_event(event)

        if self.waiting_for_button:
            if event.type == pygame.JOYBUTTONDOWN:
                self.button_number = event.button
                self.waiting_for_button = False
                self.on_button_change(event.button)
                self.on_remap_toggle(False)
                self.reset_button.enable()
                return True

            if event.type == pygame.JOYHATMOTION and event.value != (0, 0):
                mapping = {"hat": event.hat, "value": list(event.value)}
                self.button_number = mapping
                self.waiting_for_button = False
                self.on_button_change(mapping)
                self.on_remap_toggle(False)
                self.reset_button.enable()
                return True

        return False

    def set_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

        self._render_label()

        # Align to bar center to match how deadband inputs are positioned
        bar_center_y = y + self.BAR_HEIGHT // 2

        self.label_rect.topleft = (x, y)
        self.label_rect.centery = bar_center_y

        self.button_text_center = (self.x + self.BUTTON_TEXT_OFFSET_X, bar_center_y)

        # Center buttons vertically with the bar
        button_height = self.remap_button.get_size()[1]
        button_y = bar_center_y - button_height // 2

        remap_button_x = self.x + self.REMAP_BUTTON_OFFSET_X
        self.remap_button.set_position(remap_button_x, button_y)

        # Position reset button next to remap button
        reset_button_x = remap_button_x + self.remap_button.get_size()[0] + self.PADDING
        self.reset_button.set_position(reset_button_x, button_y)

    def get_size(self) -> tuple[int, int]:
        button_height = max(self.remap_button.get_size()[1], self.reset_button.get_size()[1])
        height = max(self.label_rect.height, button_height)
        width = self.WIDTH + self.remap_button.get_size()[0] + self.PADDING + self.reset_button.get_size()[0]

        return (width, height)

    def enable(self) -> None:
        self.remap_button.enable()
        # Only enable reset if there's a button mapped
        if self.button_number is not None:
            self.reset_button.enable()

    def disable(self) -> None:
        self.remap_button.disable()
        self.reset_button.disable()

    def _render_label(self) -> None:
        self.label_surface, self.label_rect = self.font.render(self.control_name, self.FONT_COLOR)
        self.label_rect.topleft = (self.x, self.y)

    def _on_remap_click(self) -> None:
        self.waiting_for_button = True
        self.button_number = None
        self.on_remap_toggle(True)

    def _on_reset_click(self) -> None:
        self.button_number = None
        self.on_button_change(None)
        self.reset_button.disable()

    def _draw(self, surface: Surface) -> None:
        self.remap_button.draw(surface)
        self.reset_button.draw(surface)

        surface.blit(self.label_surface, self.label_rect)

        if self.waiting_for_button:
            button_label = "---"
        else:
            button_label = format_mapping(self.button_number)

        button_surface, button_rect = self.font.render(button_label, self.FONT_COLOR)
        button_rect.midleft = self.button_text_center
        surface.blit(button_surface, button_rect)
