from pygame import Surface

from v3xctrl_ui.osd.widgets.Widget import Widget
from v3xctrl_ui.utils.colors import GREEN, GREY, ORANGE, RED
from v3xctrl_ui.utils.helpers import get_icon


class GpsIconWidget(Widget):
    def __init__(self, position: tuple[int, int], width: int) -> None:
        self.position = position
        self.width = width
        self.height = width

        self.icon_no_hardware = get_icon("satellite_alt", size=width, color=GREY)
        self.icon_no_fix = get_icon("satellite_alt", size=width, color=RED)
        self.icon_partial_fix = get_icon("satellite_alt", size=width, color=ORANGE)
        self.icon_full_fix = get_icon("satellite_alt", size=width, color=GREEN)

    def draw(self, screen: Surface, fix_type: int) -> None:
        if fix_type < 0:
            icon = self.icon_no_hardware
        elif fix_type == 0:
            icon = self.icon_no_fix
        elif fix_type <= 2:
            icon = self.icon_partial_fix
        else:
            icon = self.icon_full_fix

        screen.blit(icon, self.position)
