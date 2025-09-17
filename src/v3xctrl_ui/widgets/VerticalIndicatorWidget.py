from typing import Tuple, Dict, Any

from pygame import draw, Surface, Rect

from v3xctrl_ui.colors import WHITE
from v3xctrl_ui.widgets.BaseIndicatorWidget import BaseIndicatorWidget

from v3xctrl_helper import clamp


class VerticalIndicatorWidget(BaseIndicatorWidget):
    def __init__(
        self,
        position: Tuple[int, int],
        size: Tuple[int, int],
        bar_width: int = 20,
        **kwargs: Dict[str, Any]
    ) -> None:
        super().__init__(position, size, **kwargs)
        self.bar_width = bar_width

        assert self.range_mode in ("symmetric", "positive"), f"Invalid range_mode: {self.range_mode}"

    def draw(self, screen: Surface, value: float) -> None:
        value = clamp(value, -1.0, 1.0)
        color = self.color_fn(value) if self.color_fn else WHITE

        self.draw_background(screen)

        if self.range_mode == "symmetric":
            offset_range = (self.height - self.padding * 2) // 2
            bar_height = int(abs(value) * offset_range)
            base_y = self.position[1] + self.height // 2
            y = base_y - bar_height if value >= 0 else base_y
        else:
            bar_height = int(value * (self.height - self.padding * 2))
            y = self.position[1] + self.height - self.padding - bar_height

        x = self.position[0] + (self.width - self.bar_width) // 2
        bar_rect = Rect(x, y, self.bar_width, bar_height)
        if bar_height > 0:
            draw.rect(screen, color, bar_rect)
            draw.rect(screen, WHITE, bar_rect, width=1)
