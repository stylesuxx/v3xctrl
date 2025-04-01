from pygame import Surface, font, Rect, SRCALPHA, draw
from typing import Tuple

from ui.colors import WHITE, GREEN, RED, YELLOW, GREY
from ui.widgets.Widget import Widget


class StatusWidget(Widget):
    STATUS_COLORS = {
        "waiting": YELLOW,
        "success": GREEN,
        "fail": RED,
        "default": GREY,
    }

    def __init__(self, position: Tuple[int, int], size: int, label: str, padding: int = 8):
        super().__init__()

        self.position = position
        self.size = size
        self.label = label
        self.padding = padding
        self.color = self.STATUS_COLORS["default"]
        self.background_alpha = 180

        font_size = 14
        self.font = font.SysFont("monospace", font_size, bold=True)

        self.label_surface = self.font.render(self.label, True, WHITE)
        label_width = self.label_surface.get_width()
        label_height = self.label_surface.get_height()

        widget_height = max(self.size, label_height)
        widget_width = self.size + self.padding + label_width + self.padding

        square_y = (widget_height - self.size) // 2

        self.label_x = self.size + self.padding
        self.label_y = (widget_height - label_height) // 2

        self.surface = Surface((widget_width, widget_height), SRCALPHA)
        self.square_rect = Rect(0, square_y, self.size, self.size)

    def set_status(self, status: str):
        self.color = self.STATUS_COLORS.get(status, self.STATUS_COLORS["default"])

    def draw(self, screen: Surface) -> None:
        self.surface.fill((0, 0, 0, self.background_alpha))

        draw.rect(self.surface, self.color, self.square_rect)

        self.surface.blit(self.label_surface, (self.label_x, self.label_y))
        self.draw_extra(self.surface)

        screen.blit(self.surface, self.position)

    def draw_extra(self, surface: Surface):
        pass  # Override in subclass to draw on top of self.surface
