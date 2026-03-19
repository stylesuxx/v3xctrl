from pygame import SRCALPHA, Surface

from v3xctrl_ui.osd.widgets.Widget import Widget
from v3xctrl_ui.utils.colors import GREEN, GREY, ORANGE, RED
from v3xctrl_ui.utils.helpers import get_icon

_BACKGROUND_ALPHA = 180


class GpsIconWidget(Widget):
    _ICON_SIZE = 46  # matches BatteryIconWidget height (int(70 / 3 * 2))

    def __init__(self, position: tuple[int, int], width: int) -> None:
        self.position = position
        self.width = width
        self.height = self._ICON_SIZE
        self._x_offset = width - self._ICON_SIZE  # right-align icon within panel width

        self._bg_surface = Surface((width, self._ICON_SIZE), SRCALPHA)
        self._bg_surface.fill((*GREY, _BACKGROUND_ALPHA))

        self.icon_no_hardware = get_icon("satellite_alt", size=self._ICON_SIZE, color=GREY)
        self.icon_no_fix = get_icon("satellite_alt", size=self._ICON_SIZE, color=RED)
        self.icon_partial_fix = get_icon("satellite_alt", size=self._ICON_SIZE, color=ORANGE)
        self.icon_full_fix = get_icon("satellite_alt", size=self._ICON_SIZE, color=GREEN)

    def draw(self, screen: Surface, fix_type: int) -> None:
        if fix_type < 0:
            icon = self.icon_no_hardware
        elif fix_type == 0:
            icon = self.icon_no_fix
        elif fix_type <= 2:
            icon = self.icon_partial_fix
        else:
            icon = self.icon_full_fix

        screen.blit(self._bg_surface, self.position)
        screen.blit(icon, (self.position[0] + self._x_offset, self.position[1]))
