import pygame
from pygame import Surface, Rect
from pygame.freetype import Font
from typing import Callable

from ui.menu.BaseWidget import BaseWidget


class Checkbox(BaseWidget):
    BOX_SIZE = 25
    BOX_MARGIN = 10

    LABEL_COLOR = (220, 220, 220)
    BG_COLOR = (255, 255, 255)
    CHECK_COLOR = (0, 0, 0)

    BORDER_LIGHT_COLOR = (180, 180, 180)
    BORDER_DARK_COLOR = (100, 100, 100)

    def __init__(self,
                 label: str,
                 font: Font,
                 checked: bool,
                 on_change: Callable[[bool], None]):
        super().__init__()

        self.label = label
        self.font = font
        self.on_change = on_change
        self.checked = checked

        self.box_rect = Rect(self.x, self.y, self.BOX_SIZE, self.BOX_SIZE)
        self.label_surface, self.label_rect = self.font.render(self.label, self.LABEL_COLOR)

        # Pre-render checkbox surface with 3D effect
        self.box_surface = pygame.Surface((self.BOX_SIZE, self.BOX_SIZE))
        self.box_surface.fill(self.BG_COLOR)

        pygame.draw.line(self.box_surface, self.BORDER_LIGHT_COLOR, (0, 0), (self.BOX_SIZE - 1, 0))  # top
        pygame.draw.line(self.box_surface, self.BORDER_LIGHT_COLOR, (0, 0), (0, self.BOX_SIZE - 1))  # left
        pygame.draw.line(self.box_surface, self.BORDER_DARK_COLOR, (0, self.BOX_SIZE - 1), (self.BOX_SIZE - 1, self.BOX_SIZE - 1))  # bottom
        pygame.draw.line(self.box_surface, self.BORDER_DARK_COLOR, (self.BOX_SIZE - 1, 0), (self.BOX_SIZE - 1, self.BOX_SIZE - 1))  # right

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.box_rect.collidepoint(event.pos) or self.label_rect.collidepoint(event.pos):
                self.checked = not self.checked
                self.on_change(self.checked)

    def set_position(self, x, y):
        self.x = x
        self.y = y

        self.box_rect.topleft = (x, y)
        self.label_rect.x = x + self.BOX_SIZE + self.BOX_MARGIN
        self.label_rect.y = y + (self.BOX_SIZE - self.label_rect.height) // 2

    def draw(self, surface: Surface):
        surface.blit(self.box_surface, self.box_rect.topleft)

        if self.checked:
            pad = 4
            pygame.draw.line(surface, self.CHECK_COLOR,
                             (self.box_rect.left + pad, self.box_rect.centery),
                             (self.box_rect.centerx, self.box_rect.bottom - pad), 2)
            pygame.draw.line(surface, self.CHECK_COLOR,
                             (self.box_rect.centerx, self.box_rect.bottom - pad),
                             (self.box_rect.right - pad, self.box_rect.top + pad), 2)

        surface.blit(self.label_surface, self.label_rect)
