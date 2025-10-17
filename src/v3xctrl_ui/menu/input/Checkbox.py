from typing import Callable, Dict

import pygame
from pygame import Surface, Rect
from pygame.freetype import Font

from v3xctrl_ui.colors import MID_GREY, WHITE, DARK_GREY, GAINSBORO
from v3xctrl_ui.menu.input import BaseWidget
from v3xctrl_ui.helpers import get_icon


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

        # Get label dimensions
        _, label_rect = self.font.render(self.label, self.LABEL_COLOR)
        self.label_width = label_rect.width
        self.label_height = label_rect.height

        # Pre-render both checkbox states with label baked in
        self.cached_surfaces: Dict[str, Surface] = {}
        self._render_checkbox_states()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.disabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check if click is within the entire checkbox area
            full_width, full_height = self.get_size()
            click_rect = Rect(self.x, self.y, full_width, full_height)

            if click_rect.collidepoint(event.pos):
                self.checked = not self.checked
                self.on_change(self.checked)

                return True

        return False

    def get_size(self) -> tuple[int, int]:
        width = self.BOX_SIZE + self.BOX_MARGIN + self.label_width
        height = max(self.BOX_SIZE, self.label_height)

        return width, height

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)
        self.box_rect.topleft = (x, y)

    def set_checked(self, checked: bool) -> None:
        if self.checked != checked:
            self.checked = checked
            self.on_change(self.checked)

    def _render_checkbox_states(self) -> None:
        """Pre-render both checkbox states WITH labels (called once at init)"""
        width, height = self.get_size()

        # Get the icon surfaces
        checkbox_icon = get_icon("circle", color=self.LABEL_COLOR)
        checkbox_checked_icon = get_icon("check_circle", color=self.LABEL_COLOR)

        states = {
            "unchecked": checkbox_icon,
            "checked": checkbox_checked_icon
        }

        # Render label once
        label_surface, label_rect = self.font.render(self.label, self.LABEL_COLOR)

        # Calculate positions relative to the surface (not screen)
        icon_x = 0
        icon_y = 0
        label_x = self.BOX_SIZE + self.BOX_MARGIN
        label_y = (height - label_rect.height) // 2

        for state in states.keys():
            surface = Surface((width, height), pygame.SRCALPHA)
            surface.fill((0, 0, 0, 0))
            surface.blit(states[state], (icon_x, icon_y))
            surface.blit(label_surface, (label_x, label_y))
            self.cached_surfaces[state] = surface

    def _draw(self, surface: Surface) -> None:
        state = 'checked' if self.checked else 'unchecked'
        surface.blit(self.cached_surfaces[state], (self.x, self.y))
