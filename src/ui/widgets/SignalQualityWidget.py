from enum import IntEnum
from pygame import Surface, Rect, SRCALPHA
from typing import Tuple

from ui.colors import WHITE, GREEN, RED, YELLOW, ORANGE, GREY
from ui.widgets.Widget import Widget


class SignalQuality(IntEnum):
    POOR = 0
    FAIR = 1
    GOOD = 2
    EXCELLENT = 3


class SignalQualityWidget(Widget):
    BAR_COUNT = 5
    SPACING_RATIO = 0.05  # relative to widget width

    def __init__(self, position: Tuple[int, int], size: Tuple[int, int]):
        super().__init__()
        self.position = position
        self.width, self.height = size

        # First calculate spacing from ratio
        self.bar_spacing = int(self.width * self.SPACING_RATIO)
        self.side_padding = 2 * self.bar_spacing

        # Compute available width for bars
        available_width = self.width - 2 * self.side_padding - (self.BAR_COUNT - 1) * self.bar_spacing
        self.bar_width = available_width // self.BAR_COUNT

        # Adjust right padding to perfectly fill the widget
        used_width = (
            self.BAR_COUNT * self.bar_width
            + (self.BAR_COUNT - 1) * self.bar_spacing
            + 2 * self.side_padding
        )
        self.extra_right_padding = self.width - used_width  # could be 0 or 1 due to rounding

        # Vertical layout
        self.top_bottom_padding = 2 * self.bar_spacing
        self.bar_max_height = self.height - 2 * self.top_bottom_padding

    def _rsrp_to_dbm(self, value: int) -> float:
        return -140 if value == 255 else value - 140

    def _rsrq_to_dbm(self, value: int) -> float:
        return -20.0 if value == 255 else (value * 0.5) - 19.5

    def _get_bars(self, value: int) -> int:
        rsrp_dbm = self._rsrp_to_dbm(value)
        if rsrp_dbm >= -80:
            return 5
        elif rsrp_dbm >= -90:
            return 4
        elif rsrp_dbm >= -100:
            return 3
        elif rsrp_dbm >= -110:
            return 2
        else:
            return 1

    def _get_quality(self, value: int) -> SignalQuality:
        rsrq_dbm = self._rsrq_to_dbm(value)
        if rsrq_dbm >= -10:
            return SignalQuality.EXCELLENT
        elif rsrq_dbm >= -15:
            return SignalQuality.GOOD
        elif rsrq_dbm >= -20:
            return SignalQuality.FAIR
        else:
            return SignalQuality.POOR

    def draw(self, screen: Surface, signal: dict) -> None:
        bars = self._get_bars(signal['rsrp'])
        quality = self._get_quality(signal['rsrq'])

        bg_color = {
            SignalQuality.POOR: RED,
            SignalQuality.FAIR: ORANGE,
            SignalQuality.GOOD: YELLOW,
            SignalQuality.EXCELLENT: GREEN
        }.get(quality, GREY)

        surface = Surface((self.width, self.height), SRCALPHA)
        surface.fill((*bg_color, 180))

        base_line = self.height - self.top_bottom_padding

        for i in range(self.BAR_COUNT):
            bar_height = int((i + 1) * self.bar_max_height / self.BAR_COUNT)
            bar_x = self.side_padding + i * (self.bar_width + self.bar_spacing)
            bar_y = base_line - bar_height

            color = WHITE if i < bars else GREY
            surface.fill(color, Rect(bar_x, bar_y, self.bar_width, bar_height))

        screen.blit(surface, self.position)
