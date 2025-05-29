from pygame import Surface, Rect, SRCALPHA
from typing import Tuple
from v3xctrl_ui.colors import WHITE, GREY
from v3xctrl_ui.fonts import BOLD_MONO_FONT
from v3xctrl_ui.widgets.Widget import Widget


class TextWidget(Widget):
    def __init__(self, position: Tuple[int, int], length: int, top_padding: int = 4, bottom_padding: int = 4):
        super().__init__()

        self.position = position
        self.length = length
        self.top_padding = top_padding
        self.bottom_padding = bottom_padding
        self.background_alpha = 180

        self.font = BOLD_MONO_FONT
        self.color = WHITE
        self.bg_color = GREY

        # Default state
        self.text_surface = None
        self.text_rect = Rect(0, 0, 0, 0)
        self.widget_height = 0
        self.surface = None

    def draw(self, screen: Surface, text: str) -> None:
        # Re-render text
        self.text_surface, self.text_rect = self.font.render(text, self.color)
        self.widget_height = self.text_rect.height + self.top_padding + self.bottom_padding
        self.surface = Surface((self.length, self.widget_height), SRCALPHA)
        self.surface.fill((*self.bg_color[:3], self.background_alpha))

        text_x = (self.length - self.text_rect.width) // 2
        text_y = self.top_padding
        self.surface.blit(self.text_surface, (text_x, text_y))

        screen.blit(self.surface, self.position)
