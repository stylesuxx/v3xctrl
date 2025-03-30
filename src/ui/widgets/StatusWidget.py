import pygame
from pygame import Surface
from typing import Tuple

from ui.widgets.Widget import Widget
from ui.colors import WHITE, GREEN, RED, YELLOW, GREY


class StatusWidget(Widget):
    WAITING_COLOR = YELLOW
    SUCCESS_COLOR = GREEN
    FAIL_COLOR = RED
    DEFAULT_COLOR = GREY

    def __init__(self, position: Tuple[int, int], size: int, label: str, padding: int = 8):
        super().__init__()

        self.position = position
        self.size = size
        self.label = label
        self.padding = padding
        self.color = self.DEFAULT_COLOR
        self.background_alpha = 180

    def set_status(self, status: str):
        if status == "waiting":
            self.color = self.WAITING_COLOR
        elif status == "success":
            self.color = self.SUCCESS_COLOR
        elif status == "fail":
            self.color = self.FAIL_COLOR
        else:
            self.color = self.DEFAULT_COLOR

    def draw(self, screen: Surface) -> None:
        font_size = 14
        font = pygame.font.SysFont("monospace", font_size, bold=True)

        label_surface = font.render(self.label, True, WHITE)
        label_width = label_surface.get_width()
        label_height = label_surface.get_height()

        widget_height = max(self.size, label_height)
        widget_width = self.size + self.padding + label_width + self.padding

        widget_surface = Surface((widget_width, widget_height), pygame.SRCALPHA)
        widget_surface.fill((0, 0, 0, self.background_alpha))

        square_y = (widget_height - self.size) // 2
        square_rect = pygame.Rect(0, square_y, self.size, self.size)
        pygame.draw.rect(widget_surface, self.color, square_rect)

        label_x = self.size + self.padding
        label_y = (widget_height - label_height) // 2
        widget_surface.blit(label_surface, (label_x, label_y))

        screen.blit(widget_surface, self.position)
