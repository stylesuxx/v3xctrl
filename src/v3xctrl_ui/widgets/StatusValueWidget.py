from collections import deque
from pygame import Surface
from typing import Tuple

from v3xctrl_ui.colors import BLACK
from v3xctrl_ui.fonts import SMALL_MONO_FONT
from v3xctrl_ui.widgets.StatusWidget import StatusWidget


class StatusValueWidget(StatusWidget):
    def __init__(
        self,
        position: Tuple[int, int],
        size: int,
        label: str,
        padding_label: int = 8,
        padding_value: int = 8,
        average: bool = False,
        average_window: int = 10,
    ) -> None:
        super().__init__(position, size, label, padding_label)

        self.padding_value = padding_value

        self.value = None
        self.value_font = SMALL_MONO_FONT
        self.average = average
        self.history: deque[int] = deque(maxlen=average_window)

    def set_value(self, value: int) -> None:
        if self.average:
            self.history.append(value)
            value = sum(self.history) // len(self.history)

        self.value = value

    def draw_extra(self, surface: Surface) -> None:
        if self.value is None:
            return

        text = str(self.value)

        """
        We can center horizontally, but we can't center vertically because fonts
        are complicated and two values might not have the same height.

        This means we need absolute positioning from the top, otherwise the
        font might seem like it jumps.
        """
        text_rect = self.value_font.get_rect(text)
        text_rect.centerx = self.square_rect.centerx
        text_rect.top = self.padding_value

        self.value_font.render_to(surface, text_rect.topleft, text, BLACK)
