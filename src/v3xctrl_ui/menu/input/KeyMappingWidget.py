from typing import Callable

import pygame
from pygame import Surface
from pygame.freetype import Font

from v3xctrl_ui.menu.input import Button, BaseWidget
from v3xctrl_ui.utils.colors import WHITE


class KeyMappingWidget(BaseWidget):
    FONT_COLOR = WHITE

    def __init__(
        self,
        control_name: str,
        key_code: int,
        font: Font,
        on_key_change: Callable[[int], None],
        on_remap_toggle: Callable[[bool], None]
    ) -> None:
        super().__init__()

        self.control_name = control_name
        self.key_code = key_code
        self.font = font
        self.on_key_change = on_key_change
        self.on_remap_toggle = on_remap_toggle

        self.waiting_for_key = False
        self.column_width = 0  # Will be set by InputTab via set_column_width()

        self.remap_button = Button("Remap", font, self._on_remap_click)

        self._render_label()

    def handle_event(self, event: pygame.event.Event) -> bool:
        self.remap_button.handle_event(event)

        if self.waiting_for_key and event.type == pygame.KEYDOWN:
            self.key_code = event.key
            self.waiting_for_key = False
            self.on_key_change(event.key)
            self.on_remap_toggle(False)

            return True

        return False

    def set_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

        self._render_label()

        row_height = max(self.label_rect.height, 30)
        center_y = y + row_height // 2

        self.label_rect.topleft = (x, y)
        self.label_rect.centery = center_y

        # Position remap button on the right edge of the column
        button_width = self.remap_button.get_size()[0]
        button_x = self.x + self.column_width - button_width

        self.remap_button.set_position(button_x, y)
        self.key_text_center = (self.x + 160, center_y)

    def get_size(self) -> tuple[int, int]:
        button_height = self.remap_button.get_size()[1]
        height = max(self.label_rect.height, button_height)

        return (self.column_width, height)

    def enable(self) -> None:
        self.remap_button.enable()

    def disable(self) -> None:
        self.remap_button.disable()

    def set_column_width(self, width: int) -> None:
        self.column_width = width

    def _render_label(self) -> None:
        self.label_surface, self.label_rect = self.font.render(self.control_name, self.FONT_COLOR)
        self.label_rect.topleft = (self.x, self.y)

    def _on_remap_click(self) -> None:
        self.waiting_for_key = True
        self.key_code = None
        self.on_remap_toggle(True)

    def _draw(self, surface: Surface) -> None:
        self.remap_button.draw(surface)

        surface.blit(self.label_surface, self.label_rect)

        key_label = "---" if self.key_code is None else pygame.key.name(self.key_code)
        key_surface, key_rect = self.font.render(key_label, self.FONT_COLOR)
        key_rect.midleft = self.key_text_center
        surface.blit(key_surface, key_rect)
