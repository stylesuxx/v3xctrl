import pygame
from pygame import Surface, Rect
from pygame.freetype import Font
import pygame.gfxdraw
from typing import Callable

from v3xctrl_ui.colors import MID_GREY, WHITE, DARK_GREY, GAINSBORO
from .BaseWidget import BaseWidget


class Checkbox(BaseWidget):
    BOX_SIZE = 25
    BOX_MARGIN = 10

    LABEL_COLOR = GAINSBORO
    BG_COLOR = WHITE
    CHECK_COLOR = MID_GREY
    BORDER_COLOR = DARK_GREY

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

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.box_rect.collidepoint(event.pos) or self.label_rect.collidepoint(event.pos):
                self.checked = not self.checked
                self.on_change(self.checked)

    def get_size(self) -> tuple[int, int]:
        width = self.BOX_SIZE + self.BOX_MARGIN + self.label_rect.width
        height = max(self.BOX_SIZE, self.label_rect.height)
        return width, height

    def set_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

        self.box_rect.topleft = (x, y)
        self.label_rect.x = x + self.BOX_SIZE + self.BOX_MARGIN
        self.label_rect.centery = self.box_rect.centery

    def set_checked(self, checked: bool) -> None:
        if self.checked != checked:
            self.checked = checked
            self.on_change(self.checked)

    def draw(self, surface: Surface) -> None:
        # Draw outer rounded rectangle (always shown)
        pygame.draw.rect(surface, self.BG_COLOR, self.box_rect, border_radius=4)
        pygame.draw.rect(surface, self.BORDER_COLOR, self.box_rect, width=1, border_radius=4)

        # Draw inner circle if checked
        if self.checked:
            center = self.box_rect.center
            radius = self.BOX_SIZE // 2 - 4
            pygame.gfxdraw.filled_circle(surface, center[0], center[1], radius, self.CHECK_COLOR)
            pygame.gfxdraw.aacircle(surface, center[0], center[1], radius, self.CHECK_COLOR)

        # Draw label
        surface.blit(self.label_surface, self.label_rect)
