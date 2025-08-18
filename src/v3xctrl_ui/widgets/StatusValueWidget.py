from typing import Tuple

from pygame import Surface

from v3xctrl_ui.colors import BLACK
from v3xctrl_ui.fonts import SMALL_MONO_FONT
from v3xctrl_ui.widgets.StatusWidget import StatusWidget


class StatusValueWidget(StatusWidget):
    def __init__(
        self,
        position: Tuple[int, int],
        size: int,
        label: str,
        padding: int = 8
    ) -> None:
        super().__init__(position, size, label, padding)
        self.value = None
        self.value_font = SMALL_MONO_FONT

    def set_value(self, value: int) -> None:
        self.value = value

    def draw_extra(self, surface: Surface) -> None:
        if self.value is not None:
            value_surface, value_surface_rect = self.value_font.render(str(self.value), BLACK)
            value_surface_rect.center = self.square_rect.center
            surface.blit(value_surface, value_surface_rect)
