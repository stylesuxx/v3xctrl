from enum import Enum
from typing import Tuple

from pygame import Surface, SRCALPHA

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

        """
        Default state - we always want the widget to be same height no matter
        of the actual text. Therefore we have to make sure to measure with all
        the valid characters
        """
        reference_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        _, reference_rect = self.font.render(reference_text)
        max_char_height = reference_rect.height
        self.height = max_char_height + self.top_padding + self.bottom_padding
        self.width = length

        self._create_background()

    def set_alignment(self, align: Alignment) -> None:
        self.alignment = align

    def set_text_color(self, color: Tuple[int, int, int]) -> None:
        self.color = color

    def set_background_color(self, color: Tuple[int, int, int], alpha: int = 180) -> None:
        self.bg_color = color
        self.background_alpha = alpha
        self._create_background()

    def draw(self, screen: Surface, text: str) -> None:
        self.text_surface, self.text_rect = self.font.render(text, self.color)
        self.surface = self.bg_surface.copy()

        match self.alignment:
            case Alignment.LEFT:
                text_x = self.left_padding
            case Alignment.CENTER:
                text_x = (self.length - self.text_rect.width) // 2
            case Alignment.RIGHT:
                text_x = self.length - self.text_rect.width - self.right_padding

        text_y = self.top_padding
        self.surface.blit(self.text_surface, (text_x, text_y))

        screen.blit(self.surface, self.position)

    def _create_background(self) -> None:
        self.bg_surface = Surface((self.length, self.height), SRCALPHA)
        self.bg_surface.fill((*self.bg_color[:3], self.background_alpha))
