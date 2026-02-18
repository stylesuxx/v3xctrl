from datetime import datetime
from typing import Tuple

import pygame.freetype
from pygame import Surface, SRCALPHA

from v3xctrl_ui.utils.colors import WHITE, BLACK

from v3xctrl_ui.osd.widgets.Widget import Widget


class ClockWidget(Widget):
    """Widget that displays current wall clock time with millisecond precision."""

    def __init__(
        self,
        position: Tuple[int, int],
        top_padding: int = 16,
        bottom_padding: int = 14,
        left_padding: int = 20,
        right_padding: int = 20
    ) -> None:
        super().__init__()

        self.position = position
        self.top_padding = top_padding
        self.bottom_padding = bottom_padding
        self.left_padding = left_padding
        self.right_padding = right_padding
        self.background_alpha = 255

        self.font = pygame.freetype.SysFont("monospace", 64, bold=True)
        self.bg_color = BLACK
        self.color = WHITE

        # Calculate size based on time format "HH:MM:SS.mmm"
        reference_text = "00:00:00.000"
        text_surface, text_rect = self.font.render(reference_text)
        self.text_width = text_rect.width
        self.text_height = text_rect.height

        self.width = self.text_width + self.left_padding + self.right_padding
        self.height = self.text_height + self.top_padding + self.bottom_padding

        self._create_background()

    def draw(self, screen: Surface, _value=None) -> None:
        """Draw the clock widget with current time."""
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S") + f".{now.microsecond // 1000:03d}"

        text_surface, text_rect = self.font.render(time_str, self.color)

        self.surface = self.bg_surface.copy()
        text_x = self.left_padding
        text_y = self.top_padding
        self.surface.blit(text_surface, (text_x, text_y))

        screen.blit(self.surface, self.position)

    def _create_background(self) -> None:
        self.bg_surface = Surface((self.width, self.height), SRCALPHA)
        self.bg_surface.fill((*self.bg_color[:3], self.background_alpha))
