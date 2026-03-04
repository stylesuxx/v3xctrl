from abc import abstractmethod
from collections.abc import Callable

from pygame import Surface, SRCALPHA

from v3xctrl_ui.osd.widgets.Widget import Widget


class BaseIndicatorWidget(Widget):
    VALID_RANGE_MODES = {"symmetric", "positive"}

    def __init__(
        self,
        position: tuple[int, int],
        size: tuple[int, int],
        range_mode: str = "symmetric",
        color_fn: Callable[[float], tuple[int, int, int]] | None = None,
        bg_alpha: int = 150,
        padding: int = 6
    ) -> None:
        """
        position: (x, y) position of the indicator background
        size: (width, height) of the total indicator area
        range_mode: 'symmetric' for [-1,1], 'positive' for [0,1]
        color_fn: function mapping value -> RGB tuple
        """
        if range_mode not in self.VALID_RANGE_MODES:
            raise ValueError(f"Invalid range_mode '{range_mode}'. Must be one of: {self.VALID_RANGE_MODES}")

        self.position = position
        self.width, self.height = size
        self.range_mode = range_mode
        self.color_fn = color_fn
        self.bg_alpha = bg_alpha
        self.padding = padding
        self.inverted = False

    @abstractmethod
    def draw(self, screen: Surface, value: float) -> None:
        pass

    def draw_background(self, screen: Surface) -> None:
        surf = Surface((self.width, self.height), SRCALPHA)
        surf.fill((0, 0, 0, self.bg_alpha))
        screen.blit(surf, self.position)
