from typing import Tuple


from pygame import Surface

from v3xctrl_ui.utils.colors import GREEN, RED, YELLOW, ORANGE
from v3xctrl_ui.osd.widgets.Widget import Widget
from v3xctrl_ui.utils.helpers import get_icon


class BatteryIconWidget(Widget):
    def __init__(self, position: Tuple[int, int], width: int) -> None:
        self.position = position

        self.width = width
        self.height = int(width / 3 * 2)
        self.offset = int((self.width - self.height) // 2)

        self.states = [
            get_icon("battery_0_bar", size=self.width, color=RED, rotation=-90),
            get_icon("battery_1_bar", size=self.width, color=ORANGE, rotation=-90),
            get_icon("battery_2_bar", size=self.width, color=ORANGE, rotation=-90),
            get_icon("battery_3_bar", size=self.width, color=YELLOW, rotation=-90),
            get_icon("battery_4_bar", size=self.width, color=YELLOW, rotation=-90),
            get_icon("battery_5_bar", size=self.width, color=GREEN, rotation=-90),
            get_icon("battery_6_bar", size=self.width, color=GREEN, rotation=-90),
            get_icon("battery_full", size=self.width, color=GREEN, rotation=-90),
        ]

    def draw(self, screen: Surface, percent: int) -> None:
        match percent:
            case _ if percent > 95:
                state = 7
            case _ if percent > 85:
                state = 6
            case _ if percent > 70:
                state = 5
            case _ if percent > 55:
                state = 4
            case _ if percent > 40:
                state = 3
            case _ if percent > 25:
                state = 2
            case _ if percent > 10:
                state = 1
            case _:
                state = 0

        position = (self.position[0], self.position[1] - self.offset)
        screen.blit(self.states[state], position)
