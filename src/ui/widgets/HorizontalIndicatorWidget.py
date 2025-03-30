from pygame import draw, Surface
from typing import Tuple

from ui.widgets.BaseIndicatorWidget import BaseIndicatorWidget
from ui.colors import WHITE


class HorizontalIndicatorWidget(BaseIndicatorWidget):
    def __init__(self,
                 pos: Tuple[int, int],
                 size: Tuple[int, int],
                 bar_size:  Tuple[int, int] = (20, 10),
                 **kwargs):
        super().__init__(pos, size, **kwargs)
        self.bar_width, self.bar_height = bar_size

    def draw(self, screen: Surface, value: float):
        value = max(-1.0, min(1.0, value))
        self.draw_background(screen)

        if self.range_mode == "symmetric":
            offset_range = (self.width - self.bar_width) // 2
            offset = int(value * offset_range)
            center_x = self.pos[0] + self.width // 2
            x = center_x - self.bar_width // 2 + offset
        else:
            offset_range = self.width - self.bar_width - self.padding * 2
            x = self.pos[0] + self.padding + int(value * offset_range)

        y = self.pos[1] + (self.height - self.bar_height) // 2
        color = self.color_fn(value) if self.color_fn else WHITE
        draw.rect(screen, color, (x, y, self.bar_width, self.bar_height))
