from pygame import Surface

from v3xctrl_ui.core.dataclasses import GpsFixType
from v3xctrl_ui.osd.widgets.Widget import Widget
from v3xctrl_ui.utils.colors import GREEN, GREY, ORANGE, RED
from v3xctrl_ui.utils.helpers import get_icon


class GpsIconWidget(Widget):
    _ICON_SIZE = 46  # matches BatteryIconWidget height (int(70 / 3 * 2))

    def __init__(self, position: tuple[int, int], width: int) -> None:
        self.position = position
        self.width = width
        self.height = self._ICON_SIZE
        self._x_offset = width - self._ICON_SIZE  # right-align icon within panel width

        self.icon_no_hardware = get_icon("satellite_alt", size=self._ICON_SIZE, color=GREY)
        self.icon_no_fix = get_icon("satellite_alt", size=self._ICON_SIZE, color=RED)
        self.icon_partial_fix = get_icon("satellite_alt", size=self._ICON_SIZE, color=ORANGE)
        self.icon_full_fix = get_icon("satellite_alt", size=self._ICON_SIZE, color=GREEN)

    def draw(self, screen: Surface, fix_type: GpsFixType) -> None:
        if fix_type == GpsFixType.NO_HARDWARE:
            icon = self.icon_no_hardware
        elif fix_type == GpsFixType.NO_FIX:
            icon = self.icon_no_fix
        elif fix_type <= GpsFixType.FIX_2D:
            icon = self.icon_partial_fix
        else:
            icon = self.icon_full_fix

        screen.blit(icon, (self.position[0] + self._x_offset, self.position[1]))
