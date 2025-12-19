from enum import Enum
from typing import Tuple

from pygame import Surface, Rect, SRCALPHA

from v3xctrl_ui.utils.colors import WHITE, GREY
from v3xctrl_ui.utils.fonts import BOLD_MONO_FONT
from v3xctrl_ui.osd.widgets.Widget import Widget


class Alignment(Enum):
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"


class TextWidget(Widget):
    def __init__(
        self,
        position: Tuple[int, int],
        length: int,
        top_padding: int = 5,
        bottom_padding: int = 3,
        left_padding: int = 4,
        right_padding: int = 4
    ) -> None:
        super().__init__()

        self.position = position
        self.length = length
        self.top_padding = top_padding
        self.bottom_padding = bottom_padding
        self.left_padding = left_padding
        self.right_padding = right_padding
        self.background_alpha = 180

        self.font = BOLD_MONO_FONT
        self.bg_color = GREY

        # Set defaults, can be overwritten
        self.color = WHITE
        self.alignment = Alignment.CENTER

        # Default state
        reference_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        _, reference_rect = self.font.render(reference_text)
        max_char_height = reference_rect.height
        self.height = max_char_height + self.top_padding + self.bottom_padding
        self.width = length

        # Pre-create background
        self.bg_surface = Surface((self.length, self.height), SRCALPHA)
        self.bg_surface.fill((*self.bg_color[:3], self.background_alpha))

        # Cache variables - initialize to None
        self._cached_text = None
        self._cached_text_surface = None
        self._cached_text_rect = None

    def set_alignment(self, align: Alignment) -> None:
        self.alignment = align

    def set_text_color(self, color: Tuple[int, int, int]) -> None:
        self.color = color

    def draw(self, screen: Surface, text: str) -> None:
        # Re-render text
        self.text_surface, self.text_rect = self.font.render(text, self.color)
        self.surface = self.bg_surface.copy()

        text_x = self.left_padding
        if self.alignment == Alignment.CENTER:
            text_x = (self.length - self.text_rect.width) // 2
        if self.alignment == Alignment.RIGHT:
            text_x = self.length - self.text_rect.width - self.right_padding

        text_y = self.top_padding
        self.surface.blit(self.text_surface, (text_x, text_y))

        screen.blit(self.surface, self.position)
