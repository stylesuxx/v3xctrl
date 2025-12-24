from typing import Callable, Tuple, Optional, Dict

import pygame
from pygame import Rect, Surface
from pygame.freetype import Font

from v3xctrl_ui.utils.helpers import render_text_full_height
from v3xctrl_ui.menu.input.BaseWidget import BaseWidget
from v3xctrl_ui.utils.colors import (
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

    BORDER_WIDTH = 3
    BORDER_RADIUS = 8
    ANTI_ALIAS_SCALE = 16

    def __init__(
        self,
        label: str,
        font: Font,
        callback: Callable[[], None],
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> None:
        super().__init__()

        self.label = label
        self.font = font
        self.callback = callback

        _, temp_rect = self.font.render(self.label)

        vertical_padding = int(font.size / 100 * 40)
        horizontal_padding = font.size

        calculated_height = font.size + vertical_padding * 2
        calculated_width = temp_rect.width + horizontal_padding * 2

        if width:
            calculated_width = width

        if height:
            calculated_height = height

        self.rect = Rect(0, 0, calculated_width, calculated_height)

        self.hovered = False
        self.focused = False
        self.disabled = False

        self._render_label(self.FONT_COLOR)

        self.cached_surfaces: Dict[str, Surface] = {}
        self._render_all_button_states()
        self._current_state = 'normal'

    def get_size(self) -> tuple[int, int]:
        return self.rect.width, self.rect.height

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)

        self.rect.topleft = (x, y)
        self._update_label_position()

    def disable(self) -> None:
        self.disabled = True
        self._render_label(self.FONT_COLOR_DISABLED)
        self._update_state()

    def enable(self) -> None:
        self.disabled = False
        self._render_label(self.FONT_COLOR)
        self._update_state()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.disabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            was_hovered = self.hovered
            self.hovered = self.rect.collidepoint(event.pos)

            if was_hovered != self.hovered:
                self._update_state()

            return self.hovered

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.focused = True
                self._update_state()

                return True

            return False

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_focused = self.focused
            if self.focused and self.rect.collidepoint(event.pos):
                self.callback()
            self.focused = False
            self.disabled = False
            self._update_state()

            return was_focused

        return False

    def _update_state(self) -> None:
        """Determine the current visual state"""
        if self.disabled:
            self._current_state = 'disabled'
        elif self.focused:
            self._current_state = 'active'
        elif self.hovered:
            self._current_state = 'hover'
        else:
            self._current_state = 'normal'

    def _update_label_position(self) -> None:
        self.label_rect.center = self.rect.center

    def _render_label(self, color: Tuple[int, int, int]) -> None:
        self.label_surface = render_text_full_height(self.font, self.label, color)
        self.label_rect = self.label_surface.get_rect(center=self.rect.center)

    def _draw(self, surface: Surface) -> None:
        button_surface = self.cached_surfaces[self._current_state]
        surface.blit(button_surface, self.rect.topleft)

    def _render_all_button_states(self) -> None:
        """Pre-render all button states WITH labels (EXPENSIVE - only called once)"""
        states = {
            'normal': (self.BG_COLOR, self.FONT_COLOR),
            'hover': (self.HOVER_COLOR, self.FONT_COLOR),
            'active': (self.ACTIVE_COLOR, self.FONT_COLOR),
            'disabled': (self.BG_COLOR_DISABLED, self.FONT_COLOR_DISABLED),
        }

        for state_name, (bg_color, font_color) in states.items():
            temp_surface = Surface((
                self.width * self.ANTI_ALIAS_SCALE,
                self.height * self.ANTI_ALIAS_SCALE,
            ), pygame.SRCALPHA)

            # Background
            pygame.draw.rect(
                temp_surface,
                bg_color,
                temp_surface.get_rect(),
                border_radius=self.BORDER_RADIUS * self.ANTI_ALIAS_SCALE
            )

            # Border
            pygame.draw.rect(
                temp_surface,
                self.BORDER_COLOR,
                temp_surface.get_rect(),
                width=self.BORDER_WIDTH * self.ANTI_ALIAS_SCALE,
                border_radius=self.BORDER_RADIUS * self.ANTI_ALIAS_SCALE
            )

            # Smoothscale down (expensive operation)
            target_size = (self.rect.width, self.rect.height)
            button_surface = pygame.transform.smoothscale(temp_surface, target_size)

            # Add label
            label_surface, label_rect = self.font.render(self.label, font_color)
            label_rect.center = (self.rect.width // 2, self.rect.height // 2)
            button_surface.blit(label_surface, label_rect)

            # Store the complete button (background + border + label)
            self.cached_surfaces[state_name] = button_surface
