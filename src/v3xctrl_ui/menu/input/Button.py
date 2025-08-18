from typing import Callable, Tuple

import pygame
from pygame import Rect, Surface
from pygame.freetype import Font

from v3xctrl_ui.menu.input.BaseWidget import BaseWidget
from v3xctrl_ui.colors import (
    CHARCOAL,
    DARK_GREY,
    GREY,
    LIGHT_GREY,
    MID_GREY,
    WHITE,
)


class Button(BaseWidget):
    FONT_COLOR = WHITE
    FONT_COLOR_DISABLED = LIGHT_GREY

    BG_COLOR = GREY
    HOVER_COLOR = MID_GREY
    ACTIVE_COLOR = DARK_GREY
    BG_COLOR_DISABLED = CHARCOAL

    BORDER_COLOR = LIGHT_GREY

    BORDER_WIDTH = 2
    BORDER_RADIUS = 8

    def __init__(
        self,
        label: str,
        width: int,
        height: int,
        font: Font,
        callback: Callable[[], None]
    ) -> None:
        super().__init__()

        self.label = label
        self.rect = Rect(0, 0, width, height)
        self.font = font
        self.callback = callback

        self.hovered = False
        self.focused = False
        self.disabled = False

        self._render_label(self.FONT_COLOR)

    def get_size(self) -> tuple[int, int]:
        return self.rect.width, self.rect.height

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)

        self.rect.topleft = (x, y)
        self._update_label_position()

    def disable(self) -> None:
        self.disabled = True
        self._render_label(self.FONT_COLOR_DISABLED)

    def enable(self) -> None:
        self.disabled = False
        self._render_label(self.FONT_COLOR)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.disabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return self.hovered

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.focused = True
                return True

            return False

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_focused = self.focused
            if self.focused and self.rect.collidepoint(event.pos):
                self.callback()
            self.focused = False
            return was_focused

        return False

    def _update_label_position(self) -> None:
        self.label_rect.center = self.rect.center

    def _render_label(self, color: Tuple[int, int, int]) -> None:
        self.label_surface, self.label_rect = self.font.render(self.label, color)
        self._update_label_position()

    def _draw(self, surface: Surface) -> None:
        if self.disabled:
            color = self.BG_COLOR_DISABLED
        elif self.focused:
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
