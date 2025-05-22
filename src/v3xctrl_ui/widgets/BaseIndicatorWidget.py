from pygame import Surface, SRCALPHA
from typing import Callable, Tuple, Optional
from abc import abstractmethod

from v3xctrl_ui.widgets.Widget import Widget


class BaseIndicatorWidget(Widget):
    VALID_RANGE_MODES = {"symmetric", "positive"}

    def __init__(self,
                 pos: Tuple[int, int],
                 size: Tuple[int, int],
                 range_mode: str = "symmetric",
                 color_fn: Optional[Callable[[float], Tuple[int, int, int]]] = None,
                 bg_alpha: int = 150,
                 padding: int = 6):
        """
        pos: (x, y) position of the indicator background
        size: (width, height) of the total indicator area
        range_mode: 'symmetric' for [-1,1], 'positive' for [0,1]
        color_fn: function mapping value -> RGB tuple
        """
        if range_mode not in self.VALID_RANGE_MODES:
            raise ValueError(f"Invalid range_mode '{range_mode}'. Must be one of: {self.VALID_RANGE_MODES}")

        self.pos = pos
        self.width, self.height = size
        self.range_mode = range_mode
        self.color_fn = color_fn
        self.bg_alpha = bg_alpha
        self.padding = padding

    @abstractmethod
    def draw(self, screen: Surface, value: float):
        pass

    def draw_background(self, screen: Surface):
        surf = Surface((self.width, self.height), SRCALPHA)
        surf.fill((0, 0, 0, self.bg_alpha))
        screen.blit(surf, self.pos)
