from typing import Callable, List

import pygame
from pygame import Rect, Surface
from pygame.freetype import Font

from v3xctrl_ui.colors import WHITE, GREY, LIGHT_GREY, MID_GREY
from v3xctrl_ui.helpers import get_icon
from .BaseWidget import BaseWidget


class Select(BaseWidget):
    FONT_COLOR = WHITE
    FONT_COLOR_DISABLED = LIGHT_GREY

    BG_COLOR = GREY
    HOVER_COLOR = MID_GREY
    BORDER_COLOR = LIGHT_GREY

    BORDER_WIDTH = 1
    OPTION_HEIGHT = 30
    CARET_PADDING = 10
    LABEL_PADDING = 10

    def __init__(
        self,
        label: str,
        label_width: int,
        length: int,
        font: Font,
        callback: Callable[[int], None],
        selected_index: int = 0
    ) -> None:
        super().__init__()

        self.label = label
        self.label_width = label_width
        self.length = length
        self.font = font
        self.callback = callback

        self.selected_index = selected_index
        self.expanded = False
        self.hover_index = -1
        self.disabled = False

        self.rect = None

        self.option_surfaces: List[Surface] = []
        self.options = []
        self.option_rects: List[Rect] = []
        self.full_expanded_rect = None

        self.label_surface, self.label_rect = self.font.render(label, self.FONT_COLOR)
        self.caret_surface = get_icon("arrow_drop_down", size=60, color=self.FONT_COLOR)

    def disable(self) -> None:
        self.disabled = True
        self._render_label_and_caret()

    def enable(self) -> None:
        self.disabled = False
        self._render_label_and_caret()

    def get_size(self) -> tuple[int, int]:
        width = self.label_width + self.LABEL_PADDING + self.length
        height = self.rect.height

        return width, height

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)

        self.rect = Rect(x + self.label_width + self.LABEL_PADDING, y, self.length, self.OPTION_HEIGHT)
        self.label_rect.topleft = (x, y + self.rect.height // 2 - self.label_rect.height // 2)
        self._update_option_rects()

    def set_options(self, options: list[str], selected_index: int = 0) -> None:
        self.options = options
        self.selected_index = selected_index if 0 <= selected_index < len(options) else 0
        self._update_option_surfaces()
        self._update_option_rects()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.disabled or not self.options:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.expanded = not self.expanded
                return True

            elif self.expanded:
                for i, opt_rect in enumerate(self.option_rects):
                    if opt_rect.collidepoint(event.pos):
                        self.selected_index = i
                        self.expanded = False
                        self.callback(i)

                        return True
                else:
                    self.expanded = False
                    return False

        elif event.type == pygame.MOUSEMOTION and self.expanded:
            self.hover_index = -1
            for i, opt_rect in enumerate(self.option_rects):
                if opt_rect.collidepoint(event.pos):
                    self.hover_index = i
                    break

        return False

    def _render_label_and_caret(self) -> None:
        color = self.FONT_COLOR_DISABLED if self.disabled else self.FONT_COLOR
        self.label_surface, self.label_rect = self.font.render(self.label, color)

        # Restore vertical centering
        self.label_rect.topleft = (
            self.x,
            self.y + self.rect.height // 2 - self.label_rect.height // 2
        )

        self._update_option_surfaces()

    def _update_option_surfaces(self) -> None:
        self.option_surfaces = []
        color = self.FONT_COLOR_DISABLED if self.disabled else self.FONT_COLOR
        max_text_width = self.rect.width - self.CARET_PADDING * 2 - 10

        for opt in self.options:
            text = opt
            rect = self.font.get_rect(text)
            while rect.width > max_text_width and len(text) > 1:
                text = text[:-1]
                rect = self.font.get_rect(text + "...")

            if text != opt:
                text = text.rstrip() + "..."

            rendered, _ = self.font.render(text, color)
            self.option_surfaces.append(rendered)

    def _update_option_rects(self) -> None:
        self.option_rects = []
        for i in range(len(self.options)):
            rect = Rect(
                self.rect.x,
                self.rect.y + self.OPTION_HEIGHT + i * self.OPTION_HEIGHT,
                self.length,
                self.OPTION_HEIGHT
            )
            self.option_rects.append(rect)
        self.full_expanded_rect = Rect(
            self.rect.x,
            self.rect.y + self.OPTION_HEIGHT,
            self.length,
            self.OPTION_HEIGHT * len(self.options)
        )

    def _draw(self, surface: Surface) -> None:
        if not self.options:
            return

        surface.blit(self.label_surface, self.label_rect)

        pygame.draw.rect(surface, self.BG_COLOR, self.rect)
        pygame.draw.rect(surface, self.BORDER_COLOR, self.rect, self.BORDER_WIDTH)

        selected_surface = self.option_surfaces[self.selected_index]
        text_y = self.rect.centery - selected_surface.get_height() // 2
        surface.blit(selected_surface, (self.rect.x + 8, text_y))

        caret_x = self.rect.right - self.CARET_PADDING - self.caret_surface.get_width() + 20
        caret_y = self.rect.centery - self.caret_surface.get_height() // 2
        surface.blit(self.caret_surface, (caret_x, caret_y))

        if self.expanded and not self.disabled:
            if self.full_expanded_rect:
                pygame.draw.rect(surface, self.BG_COLOR, self.full_expanded_rect)
                pygame.draw.rect(surface, self.BORDER_COLOR, self.full_expanded_rect, self.BORDER_WIDTH)

            for i, opt_rect in enumerate(self.option_rects):
                bg = self.HOVER_COLOR if i == self.hover_index else self.BG_COLOR
                pygame.draw.rect(surface, bg, opt_rect)
                option_surface = self.option_surfaces[i]
                option_y = opt_rect.centery - option_surface.get_height() // 2
                surface.blit(option_surface, (opt_rect.x + 8, option_y))
