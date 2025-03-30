from pygame import draw, Surface
from typing import Tuple

from ui.widgets.BaseIndicatorWidget import BaseIndicatorWidget
from ui.colors import WHITE


class VerticalIndicatorWidget(BaseIndicatorWidget):
    def __init__(self,
                 pos: Tuple[int, int],
                 size: Tuple[int, int],
                 bar_width: int = 20,
                 **kwargs):
        super().__init__(pos, size, **kwargs)
        self.bar_width = bar_width

    def draw(self, screen: Surface, value: float):
        value = max(-1.0, min(1.0, value))
        self.draw_background(screen)

        if self.range_mode == "symmetric":
            offset_range = (self.height - self.padding * 2) // 2
            bar_height = int(abs(value) * offset_range)
            base_y = self.pos[1] + self.height // 2
            y = base_y - bar_height if value >= 0 else base_y
        else:
            bar_height = int(value * (self.height - self.padding * 2))
            y = self.pos[1] + self.height - self.padding - bar_height

        x = self.pos[0] + (self.width - self.bar_width) // 2
        color = self.color_fn(value) if self.color_fn else WHITE
        bar_height = max(0, bar_height)
        draw.rect(screen, color, (x, y, self.bar_width, bar_height))
