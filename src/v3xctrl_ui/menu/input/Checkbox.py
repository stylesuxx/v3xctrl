import io
from typing import Callable, Tuple

import pygame
from pygame import Surface, Rect
from pygame.freetype import Font

from material_icons import MaterialIcons

from v3xctrl_helper import color_to_hex
from v3xctrl_ui.colors import MID_GREY, WHITE, DARK_GREY, GAINSBORO
from v3xctrl_ui.menu.input import BaseWidget


class Checkbox(BaseWidget):
    LABEL_COLOR = GAINSBORO
    BG_COLOR = WHITE
    CHECK_COLOR = MID_GREY
    BORDER_COLOR = DARK_GREY

    BOX_SIZE = 24
    BOX_MARGIN = 5

    def __init__(
        self,
        label: str,
        font: Font,
        checked: bool,
        on_change: Callable[[bool], None]
    ) -> None:
        super().__init__()

        self.label = label
        self.font = font
        self.on_change = on_change
        self.checked = checked

        self.box_rect = Rect(self.x, self.y, self.BOX_SIZE, self.BOX_SIZE)
        self.label_surface, self.label_rect = self.font.render(self.label, self.LABEL_COLOR)

        self.icons = MaterialIcons()
        icon_color = color_to_hex(self.LABEL_COLOR)
        checkbox = self.icons.get("circle", color=icon_color)
        self.checkbox_surface = pygame.image.load(io.BytesIO(checkbox))

        checkbox_checked = self.icons.get("check_circle", color=icon_color)
        self.checkbox_checked_surface = pygame.image.load(io.BytesIO(checkbox_checked))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.disabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.box_rect.collidepoint(event.pos) or self.label_rect.collidepoint(event.pos):
                self.checked = not self.checked
                self.on_change(self.checked)

                return True

        return False

    def get_size(self) -> tuple[int, int]:
        width = self.BOX_SIZE + self.BOX_MARGIN + self.label_rect.width
        height = max(self.BOX_SIZE, self.label_rect.height)
        return width, height

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)

        self.box_rect.topleft = (x, y)
        self.label_rect.x = x + self.BOX_SIZE + self.BOX_MARGIN
        self.label_rect.centery = self.box_rect.centery

    def set_checked(self, checked: bool) -> None:
        if self.checked != checked:
            self.checked = checked
            self.on_change(self.checked)

    def _draw(self, surface: Surface) -> None:
        if self.checked:
            surface.blit(self.checkbox_checked_surface, self.box_rect)
        else:
            surface.blit(self.checkbox_surface, self.box_rect)

        surface.blit(self.label_surface, self.label_rect)
