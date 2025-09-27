from enum import IntEnum
from typing import Tuple, Dict, Any

from pygame import Surface, SRCALPHA
from material_icons import IconStyle

from v3xctrl_ui.colors import WHITE, GREEN, RED, YELLOW, ORANGE, GREY, DARK_GREY
from v3xctrl_ui.widgets.Widget import Widget
from v3xctrl_ui.helpers import get_icon


class SignalQuality(IntEnum):
    POOR = 0
    FAIR = 1
    GOOD = 2
    EXCELLENT = 3


class SignalQualityWidget(Widget):
    def __init__(self, position: Tuple[int, int], size: Tuple[int, int]) -> None:
        super().__init__()

        self.position = position
        self.width, self.height = size

        self.icon_size = 50
        self.x_offset = (self.width - self.icon_size) // 2
        self.y_offset = (self.height - self.icon_size) // 2

        # Prepare bars surfaces
        self.bars = [
            get_icon("signal_cellular_0_bar", size=self.icon_size, color=DARK_GREY, style=IconStyle.TWOTONE),
            get_icon("signal_cellular_1_bar", size=self.icon_size, color=DARK_GREY, style=IconStyle.TWOTONE),
            get_icon("signal_cellular_2_bar", size=self.icon_size, color=DARK_GREY, style=IconStyle.TWOTONE),
            get_icon("signal_cellular_3_bar", size=self.icon_size, color=DARK_GREY, style=IconStyle.TWOTONE),
            get_icon("signal_cellular_4_bar", size=self.icon_size, color=DARK_GREY, style=IconStyle.TWOTONE),
        ]

        self.no_data = get_icon(
            "signal_cellular_nodata",
            size=self.icon_size,
            color=RED
        )

    def draw(self, screen: Surface, signal: Dict[str, Any]) -> None:
        rsrp = signal.get('rsrp')
        rsrq = signal.get('rsrq')

        if rsrp in (-1, 255) or rsrq in (-1, 255):
            position = (
                self.position[0] + self.x_offset,
                self.position[1] + self.y_offset
            )
            screen.blit(self.no_data, position)
            return

        bars = self._get_bars(rsrp)
        quality = self._get_quality(rsrq)

        bg_color = {
            SignalQuality.POOR: RED,
            SignalQuality.FAIR: ORANGE,
            SignalQuality.GOOD: YELLOW,
            SignalQuality.EXCELLENT: GREEN
        }.get(quality, GREY)

        surface = Surface((self.width, self.height), SRCALPHA)
        surface.fill((*bg_color, 180))

        surface.blit(self.bars[bars], (self.x_offset, self.y_offset))
        screen.blit(surface, self.position)

    def _rsrp_to_dbm(self, value: int) -> float:
        return -140 if value == 255 else value - 140

    def _rsrq_to_dbm(self, value: int) -> float | None:
        if value == 255:
            return None
        return (value - 40) / 2

    def _get_bars(self, value: int) -> int:
        rsrp_dbm = self._rsrp_to_dbm(value)
        if rsrp_dbm >= -85:
            return 4
        elif rsrp_dbm >= -95:
            return 3
        elif rsrp_dbm >= -105:
            return 2
        elif rsrp_dbm >= -115:
            return 1
        else:
            return 0

    def _get_quality(self, value: int) -> SignalQuality:
        rsrq_dbm = self._rsrq_to_dbm(value)
        if rsrq_dbm is None:
            return SignalQuality.POOR

        if rsrq_dbm >= -9:
            return SignalQuality.EXCELLENT
        elif rsrq_dbm >= -14:
            return SignalQuality.GOOD
        elif rsrq_dbm >= -19:
            return SignalQuality.FAIR
        else:
            return SignalQuality.POOR
