
from abc import ABC, abstractmethod

import pygame
from pygame import Surface, event

from ui.colors import WHITE
from ui.fonts import MAIN_FONT


class Tab(ABC):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int):
        self.settings = settings
        self.width = width
        self.height = height
        self.padding = padding
        self.y_offset = y_offset

    def get_settings(self) -> dict:
        return self.settings

    def set_settings(self, settings: dict):
        self.settings = settings

    def _draw_headline(self, surface: Surface, title: str, y: int):
        text_surface, _ = MAIN_FONT.render(title, WHITE)
        surface.blit(text_surface, (self.padding, y))
        pygame.draw.line(surface, WHITE,
                         (self.padding, y + 40),
                         (self.width - self.padding, y + 40), 2)

        return y + 40

    @abstractmethod
    def handle_event(self, event: event.Event):
        raise NotImplementedError

    @abstractmethod
    def draw(self, surface: Surface):
        raise NotImplementedError
