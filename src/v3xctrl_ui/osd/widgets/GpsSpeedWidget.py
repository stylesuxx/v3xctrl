from pygame import SRCALPHA, Surface

from v3xctrl_ui.osd.widgets.Widget import Widget
from v3xctrl_ui.utils.colors import GREY, WHITE
from v3xctrl_ui.utils.fonts import BOLD_MONO_FONT, SMALL_MONO_FONT

_TOP_PADDING = 5
_BOTTOM_PADDING = 3
_RIGHT_PADDING = 4
_UNIT_GAP = 2


class GpsSpeedWidget(Widget):
    def __init__(self, position: tuple[int, int], width: int) -> None:
        super().__init__()
        self.position = position
        self.width = width
        self._color = WHITE

        reference_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        _, ref_rect = BOLD_MONO_FONT.render(reference_text)
        self.height = ref_rect.height + _TOP_PADDING + _BOTTOM_PADDING

        self._bg_surface = Surface((self.width, self.height), SRCALPHA)
        self._bg_surface.fill((*GREY[:3], 180))

    def draw(self, screen: Surface, speed: float) -> None:
        number_surface, number_rect = BOLD_MONO_FONT.render(f"{speed:.0f}", self._color)
        unit_surface, unit_rect = SMALL_MONO_FONT.render("km/h", self._color)

        surface = self._bg_surface.copy()

        unit_x = self.width - _RIGHT_PADDING - unit_rect.width
        number_x = unit_x - _UNIT_GAP - number_rect.width
        number_y = _TOP_PADDING
        unit_y = _TOP_PADDING + (number_rect.height - unit_rect.height)

        surface.blit(number_surface, (number_x, number_y))
        surface.blit(unit_surface, (unit_x, unit_y))

        screen.blit(surface, self.position)
