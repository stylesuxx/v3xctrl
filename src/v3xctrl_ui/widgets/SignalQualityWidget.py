from enum import IntEnum
import math
from pygame import Surface, Rect, SRCALPHA
import pygame
import pygame.gfxdraw
from typing import Tuple

from v3xctrl_ui.colors import WHITE, GREEN, RED, YELLOW, ORANGE, GREY, BLACK
from v3xctrl_ui.widgets.Widget import Widget


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
        if value == 255:
            return None
        return (value - 40) / 2

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
        elif rsrp_dbm >= -120:
            return 1
        else:
            return 0

    def _get_quality(self, value: int) -> SignalQuality:
        rsrq_dbm = self._rsrq_to_dbm(value)
        if rsrq_dbm is None:
            return SignalQuality.POOR

        if rsrq_dbm >= -7:
            return SignalQuality.EXCELLENT
        elif rsrq_dbm >= -12:
            return SignalQuality.GOOD
        elif rsrq_dbm >= -17:
            return SignalQuality.FAIR
        else:
            return SignalQuality.POOR

    def _draw_no_modem(self, screen: Surface) -> None:
        bg_surface = pygame.Surface((self.width, self.height), SRCALPHA)
        bg_surface.fill((*BLACK, 180))

        symbol_surface = pygame.Surface((self.width, self.height), SRCALPHA)

        # Geometry with same padding as bar display
        drawable_width = self.width - 2 * self.side_padding
        drawable_height = self.height - 2 * self.top_bottom_padding
        cx = self.side_padding + drawable_width // 2
        cy = self.top_bottom_padding + drawable_height // 2
        outer_radius = min(drawable_width, drawable_height) // 2 - 2
        stroke = max(2, outer_radius // 4)

        # Draw solid red ring on symbol surface
        pygame.gfxdraw.filled_circle(symbol_surface, cx, cy, outer_radius, RED)
        pygame.gfxdraw.filled_circle(symbol_surface, cx, cy, outer_radius - stroke, (0, 0, 0, 0))

        # Draw slash
        angle1 = math.radians(135)
        angle2 = math.radians(315)
        r = outer_radius - stroke // 2

        x1 = int(cx + r * math.cos(angle1))
        y1 = int(cy + r * math.sin(angle1))
        x2 = int(cx + r * math.cos(angle2))
        y2 = int(cy + r * math.sin(angle2))

        pygame.draw.line(symbol_surface, RED, (x1, y1), (x2, y2), width=stroke + 2)

        bg_surface.blit(symbol_surface, (0, 0))
        screen.blit(bg_surface, self.position)

    def draw(self, screen: Surface, signal: dict) -> None:
        rsrp = signal.get('rsrp')
        rsrq = signal.get('rsrq')

        if rsrp in (-1, 255) or rsrq in (-1, 255):
            self._draw_no_modem(screen)
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

        base_line = self.height - self.top_bottom_padding

        for i in range(self.BAR_COUNT):
            bar_height = int((i + 1) * self.bar_max_height / self.BAR_COUNT)
            bar_x = self.side_padding + i * (self.bar_width + self.bar_spacing)
            bar_y = base_line - bar_height

            color = WHITE if i < bars else GREY
            surface.fill(color, Rect(bar_x, bar_y, self.bar_width, bar_height))

        screen.blit(surface, self.position)
