from typing import Callable, Optional

import pygame
from pygame import Surface
from pygame.freetype import Font

from v3xctrl_ui.menu.input import Button, BaseWidget
from v3xctrl_ui.utils.colors import WHITE


class ButtonMappingWidget(BaseWidget):
    FONT_COLOR = WHITE
    BUTTON_TEXT_OFFSET_X = 140
    REMAP_BUTTON_OFFSET_X = 240
    PADDING = 10
    WIDTH = 260
    BAR_HEIGHT = 30  # Match GamepadCalibrationWidget.BAR_HEIGHT for alignment

    def __init__(
        self,
        control_name: str,
        button_number: Optional[int],
        font: Font,
        on_button_change: Callable[[Optional[int]], None],
        on_remap_toggle: Callable[[bool], None]
    ) -> None:
        super().__init__()

        self.control_name = control_name
        self.button_number = button_number
        self.font = font
        self.on_button_change = on_button_change
        self.on_remap_toggle = on_remap_toggle

        self.waiting_for_button = False

        self.remap_button = Button("Assign", font, self._on_remap_click)
        self.reset_button = Button("Reset", font, self._on_reset_click)

        # Disable reset button if no button is mapped
        if button_number is None:
            self.reset_button.disable()

        self._render_label()

    def handle_event(self, event: pygame.event.Event) -> bool:
        self.remap_button.handle_event(event)
        self.reset_button.handle_event(event)

        if self.waiting_for_button and event.type == pygame.JOYBUTTONDOWN:
            self.button_number = event.button
            self.waiting_for_button = False
            self.on_button_change(event.button)
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
        elif self.button_number is None:
            button_label = "N/A"
        else:
            button_label = f"Button {self.button_number}"

        button_surface, button_rect = self.font.render(button_label, self.FONT_COLOR)
        button_rect.midleft = self.button_text_center
        surface.blit(button_surface, button_rect)
