
import pygame
from pygame import Surface

from .BaseWidget import BaseWidget


class WidgetRow(BaseWidget):
    def __init__(self, children: list[BaseWidget], gap: int = 10) -> None:
        super().__init__()
        self.children = children
        self.hover_children = children
        self.gap = gap

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)
        cx = x
        for child in self.children:
            child_h = child.get_size()[1]
            child_y = y + (self.height - child_h) // 2
            child.set_position(cx, child_y)
            cx += child.get_size()[0] + self.gap

    def get_size(self) -> tuple[int, int]:
        total_w = 0
        max_h = 0
        for i, child in enumerate(self.children):
            w, h = child.get_size()
            total_w += w
            if i > 0:
                total_w += self.gap
            max_h = max(max_h, h)
        return total_w, max_h

    def handle_event(self, event: pygame.event.Event) -> bool:
        for child in self.children:
            if child.handle_event(event):
                return True
        return False

    def _draw(self, surface: Surface) -> None:
        for child in self.children:
            child.draw(surface)
