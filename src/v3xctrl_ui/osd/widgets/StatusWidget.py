from typing import ClassVar

from pygame import SRCALPHA, Rect, Surface, draw

from v3xctrl_ui.core.StatusLevel import StatusLevel
from v3xctrl_ui.osd.widgets.Widget import Widget
from v3xctrl_ui.utils.colors import GREEN, GREY, RED, WHITE, YELLOW
from v3xctrl_ui.utils.fonts import BOLD_MONO_FONT
from v3xctrl_ui.utils.helpers import round_corners


class StatusWidget(Widget[StatusLevel]):
    LEVEL_COLORS: ClassVar[dict[StatusLevel, tuple[int, int, int]]] = {
        StatusLevel.NEUTRAL: GREY,
        StatusLevel.GOOD: GREEN,
        StatusLevel.WARNING: YELLOW,
        StatusLevel.BAD: RED,
    }

    def __init__(self, position: tuple[int, int], size: int, label: str, padding: int = 8) -> None:
        super().__init__()

        self.position = position
        self.size = size
        self.label = label
        self.padding = padding
        self.color = self.LEVEL_COLORS[StatusLevel.NEUTRAL]
        self.background_alpha = 180

        self.font = BOLD_MONO_FONT

        self.label_surface, self.label_surface_rect = self.font.render(self.label, WHITE)
        label_width = self.label_surface_rect.width
        label_height = self.label_surface_rect.height

        self.height = max(self.size, label_height)
        self.width = self.size + self.padding + label_width + self.padding

        square_y = (self.height - self.size) // 2

        self.label_x = self.size + self.padding
        self.label_y = (self.height - label_height) // 2

        self.surface = Surface((self.width, self.height), SRCALPHA)
        self.square_rect = Rect(0, square_y, self.size, self.size)

    def draw(self, screen: Surface, level: StatusLevel) -> None:
        self.color = self.LEVEL_COLORS[level]

        self.surface.fill((0, 0, 0, self.background_alpha))

        draw.rect(self.surface, self.color, self.square_rect)

        self.surface.blit(self.label_surface, (self.label_x, self.label_y))
        self.draw_extra(self.surface)

        rounded = round_corners(self.surface, 6)
        screen.blit(rounded, self.position)

    def draw_extra(self, surface: Surface) -> None:
        pass
