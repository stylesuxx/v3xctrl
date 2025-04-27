from pygame import draw, Surface, Rect
from typing import Tuple

from ui.colors import WHITE
from ui.widgets.BaseIndicatorWidget import BaseIndicatorWidget
from v3xctrl_helper import clamp


class HorizontalIndicatorWidget(BaseIndicatorWidget):
    def __init__(self,
                 pos: Tuple[int, int],
                 size: Tuple[int, int],
                 bar_size:  Tuple[int, int] = (20, 10),
                 **kwargs):
        super().__init__(pos, size, **kwargs)

        self.bar_width, self.bar_height = bar_size
        self.center_x = self.pos[0] + self.width // 2
        self.y = self.pos[1] + (self.height - self.bar_height) // 2

        assert self.range_mode in ("symmetric", "positive"), f"Invalid range_mode: {self.range_mode}"

    def draw(self, screen: Surface, value: float):
        value = clamp(value, -1.0, 1.0)
        color = self.color_fn(value) if self.color_fn else WHITE

        self.draw_background(screen)

        if self.range_mode == "symmetric":
            offset_range = (self.width - self.bar_width - self.padding * 2) // 2
            offset = int(value * offset_range)
            x = self.center_x - self.bar_width // 2 + offset
        else:
            offset_range = self.width - self.bar_width - self.padding * 2
            x = self.pos[0] + self.padding + int(value * offset_range)

        bar_rect = Rect(x, self.y, self.bar_width, self.bar_height)
        draw.rect(screen, color, bar_rect)
        draw.rect(screen, WHITE, bar_rect, width=1)
