import pygame
from pygame import Surface
from pygame.freetype import Font
from typing import Callable

from v3xctrl_ui.menu.Button import Button
from v3xctrl_ui.menu.BaseWidget import BaseWidget


class KeyMappingWidget(BaseWidget):
    FONT_COLOR = (255, 255, 255)

    def __init__(self,
                 control_name: str,
                 key_code: int,
                 font: Font,
                 on_key_change: Callable[[int], None],
                 on_remap_toggle: Callable[[bool], None]):
        super().__init__()

        self.control_name = control_name
        self.key_code = key_code
        self.font = font
        self.on_key_change = on_key_change
        self.on_remap_toggle = on_remap_toggle  # now mandatory
        self.waiting_for_key = False

        self.button_x = 300

        self.remap_button = Button(
            "Remap",
            100, 30,
            font,
            self._on_remap_click
        )

        self._render_label()

    def _render_label(self):
        self.label_surface, self.label_rect = self.font.render(self.control_name, self.FONT_COLOR)
        self.label_rect.topleft = (self.x, self.y)

    def _on_remap_click(self):
        self.waiting_for_key = True
        self.key_code = None
        self.on_remap_toggle(True)

    def handle_event(self, event):
        self.remap_button.handle_event(event)

        if self.waiting_for_key and event.type == pygame.KEYDOWN:
            self.key_code = event.key
            self.waiting_for_key = False
            self.on_key_change(event.key)
            self.on_remap_toggle(False)

    def set_position(self, x, y):
        self.x = x
        self.y = y

        self._render_label()

        row_height = max(self.label_rect.height, 30)
        center_y = y + row_height // 2

        self.label_rect.topleft = (x, y)
        self.label_rect.centery = center_y

        self.remap_button.set_position(self.button_x, y)
        self.key_text_center = (self.x + 160, center_y)

    def get_size(self) -> tuple[int, int]:
        button_width, button_height = self.remap_button.get_size()
        label_width = self.label_rect.width
        key_label_width = 100  # Conservative estimate for key name width
        spacing = self.button_x - (self.x + label_width)  # gap between label and key name
        total_width = label_width + spacing + key_label_width + (button_width if self.button_x > 0 else 0)

        height = max(self.label_rect.height, button_height)
        return total_width, height

    def enable(self):
        self.remap_button.enable()

    def disable(self):
        self.remap_button.disable()

    def draw(self, surface: Surface):
        self.remap_button.draw(surface)

        surface.blit(self.label_surface, self.label_rect)

        key_label = "---" if self.key_code is None else pygame.key.name(self.key_code)
        key_surface, key_rect = self.font.render(key_label, self.FONT_COLOR)
        key_rect.midleft = self.key_text_center
        surface.blit(key_surface, key_rect)
