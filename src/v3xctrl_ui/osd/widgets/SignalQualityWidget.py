from enum import IntEnum
from typing import Tuple, Dict, Any

from pygame import Surface, SRCALPHA
from material_icons import IconStyle

from v3xctrl_ui.utils.colors import (
  WHITE,
  GREEN,
  RED,
  YELLOW,
  ORANGE,
  GREY,
)
from v3xctrl_ui.utils.helpers import get_icon

from v3xctrl_ui.osd.widgets.Widget import Widget


class SignalQuality(IntEnum):
    POOR = 0
    FAIR = 1
    GOOD = 2
    EXCELLENT = 3


class SignalQualityWidget(Widget):
    BAR_COUNT = 5
    SPACING_RATIO = 0.05
    PADDING = 16

    def __init__(self, position: Tuple[int, int], size: Tuple[int, int]) -> None:
        super().__init__()

        self.position = position
        self.width, self.height = size

        self.icon_size = 50
        self.x_offset = (self.width - self.icon_size) // 2
        self.y_offset = (self.height - self.icon_size) // 2

        self.no_data = get_icon(
            "block",
            size=self.icon_size,
            color=RED,
            style=IconStyle.OUTLINED
        )

        # First calculate spacing from ratio
        self.bar_spacing = int(self.width * self.SPACING_RATIO)

        # Compute available width for bars
        available_width = self.width - self.PADDING * 2
        self.bar_width = available_width // self.BAR_COUNT

        # Adjust right padding to perfectly fill the widget
        used_width = (
            self.BAR_COUNT * self.bar_width
            + (self.BAR_COUNT - 1) * self.bar_spacing
        )
        self.side_padding = (self.width - used_width) / 2

        # Vertical layout
        self.top_bottom_padding = 2 * self.bar_spacing
        self.bar_max_height = self.height - 2 * self.top_bottom_padding

    def draw(self, screen: Surface, signal: Dict[str, Any]) -> None:
        rsrp = signal.get('rsrp')
        rsrq = signal.get('rsrq')

        # No signal
        if rsrp in (-1, 255) or rsrq in (-1, 255):
            position = (
                self.position[0] + self.x_offset,
                self.position[1] + self.y_offset
            )
            screen.blit(self.no_data, position)

            return

        bars = self._get_bars(rsrp)
        quality = self._get_quality(rsrq)

        match quality:
            case SignalQuality.POOR:
                bg_color = RED
            case SignalQuality.FAIR:
                bg_color = ORANGE
            case SignalQuality.GOOD:
                bg_color = YELLOW
            case SignalQuality.EXCELLENT:
                bg_color = GREEN
            case _:
                bg_color = GREY

        surface = Surface((self.width, self.height), SRCALPHA)
        surface.fill((*bg_color, 180))

        base_line = self.height - self.top_bottom_padding

        for i in range(self.BAR_COUNT):
            min_height = 6
            ratio = ((i + 1) / self.BAR_COUNT) ** 1.4
            bar_height = min_height + (self.bar_max_height - min_height) * ratio
            bar_x = self.side_padding + i * (self.bar_width + self.bar_spacing)
            bar_y = base_line - bar_height

            color = WHITE if i < bars else GREY

            bar_surface = Surface((self.bar_width, bar_height))
            bar_surface.fill(color)

            surface.blit(bar_surface, (bar_x, bar_y))

        screen.blit(surface, self.position)

    def _rsrp_to_dbm(self, value: int) -> float:
        return -140 if value == 255 else value - 140

    def _rsrq_to_dbm(self, value: int) -> float | None:
        if value == 255:
            return None
        return (value - 40) / 2

    def _get_bars(self, value: int) -> int:
        rsrp_dbm = self._rsrp_to_dbm(value)
        match rsrp_dbm:
            case _ if rsrp_dbm >= -80:
                return 5
            case _ if rsrp_dbm >= -90:
                return 4
            case _ if rsrp_dbm >= -100:
                return 3
            case _ if rsrp_dbm >= -110:
                return 2
            case _ if rsrp_dbm >= -120:
                return 1
            case _:
                return 0

    def _get_quality(self, value: int) -> SignalQuality:
        rsrq_dbm = self._rsrq_to_dbm(value)
        match rsrq_dbm:
            case None:
                return SignalQuality.POOR
            case _ if rsrq_dbm >= -9:
                return SignalQuality.EXCELLENT
            case _ if rsrq_dbm >= -14:
                return SignalQuality.GOOD
            case _ if rsrq_dbm >= -19:
                return SignalQuality.FAIR
            case _:
                return SignalQuality.POOR
