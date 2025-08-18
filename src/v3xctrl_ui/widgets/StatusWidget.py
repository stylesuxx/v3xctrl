from typing import Tuple, Dict, Any

from pygame import Surface, Rect, SRCALPHA, draw

from v3xctrl_ui.colors import WHITE, GREEN, RED, YELLOW, GREY
from v3xctrl_ui.fonts import BOLD_MONO_FONT
from v3xctrl_ui.widgets.Widget import Widget


class StatusWidget(Widget):
    STATUS_COLORS: Dict[str, Any] = {
        "waiting": YELLOW,
        "success": GREEN,
        "fail": RED,
        "default": GREY,
        "green": GREEN,
        "yellow": YELLOW,
        "red": RED,
    }

    def __init__(
        self,
        position: Tuple[int, int],
        size: int,
        label: str,
        padding: int = 8
    ) -> None:
        self.position = position
        self.size = size
        self.label = label
        self.padding = padding
        self.color = self.STATUS_COLORS["default"]
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

        super().__init__()

    def draw(self, screen: Surface, status: str) -> None:
        self.color = self.STATUS_COLORS.get(status, self.STATUS_COLORS["default"])

        self.surface.fill((0, 0, 0, self.background_alpha))

        draw.rect(self.surface, self.color, self.square_rect)

        self.surface.blit(self.label_surface, (self.label_x, self.label_y))
        self.draw_extra(self.surface)

        screen.blit(self.surface, self.position)

    def draw_extra(self, surface: Surface) -> None:
        pass
