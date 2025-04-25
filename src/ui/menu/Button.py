import pygame
from typing import Callable
from pygame import Rect, Surface
from pygame.freetype import Font


class Button:
    FONT_COLOR = (255, 255, 255)
    FONT_COLOR_DISABLED = (180, 180, 180)

    BG_COLOR = (100, 100, 100)
    HOVER_COLOR = (120, 120, 120)
    ACTIVE_COLOR = (70, 70, 70)
    BG_COLOR_DISABLED = (60, 60, 60)

    BORDER_COLOR = (180, 180, 180)

    BORDER_WIDTH = 2
    BORDER_RADIUS = 8

    def __init__(self,
                 label: str,
                 width: int,
                 height: int,
                 font: Font,
                 callback: Callable):
        self.label = label
        self.rect = Rect(0, 0, width, height)
        self.font = font
        self.callback = callback

        self.hovered = False
        self.active = False
        self.disabled = False

        self._render_label(self.FONT_COLOR)

    def get_size(self) -> tuple[int, int]:
        return self.rect.width, self.rect.height

    def set_position(self, x: int, y: int):
        self.rect.topleft = (x, y)
        self._update_label_position()

    def _update_label_position(self):
        self.label_rect.center = self.rect.center

    def _render_label(self, color):
        self.label_surface, self.label_rect = self.font.render(self.label, color)
        self._update_label_position()

    def disable(self):
        self.disabled = True
        self._render_label(self.FONT_COLOR_DISABLED)

    def enable(self):
        self.disabled = False
        self._render_label(self.FONT_COLOR)

    def handle_event(self, event):
        if self.disabled:
            return

        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.active = True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.active and self.rect.collidepoint(event.pos):
                self.callback()
            self.active = False

    def draw(self, surface: Surface):
        if self.disabled:
            color = self.BG_COLOR_DISABLED
        elif self.active:
            color = self.ACTIVE_COLOR
        elif self.hovered:
            color = self.HOVER_COLOR
        else:
            color = self.BG_COLOR

        pygame.draw.rect(surface,
                         color,
                         self.rect,
                         border_radius=self.BORDER_RADIUS)
        pygame.draw.rect(surface,
                         self.BORDER_COLOR,
                         self.rect,
                         width=self.BORDER_WIDTH,
                         border_radius=self.BORDER_RADIUS)

        surface.blit(self.label_surface, self.label_rect)
