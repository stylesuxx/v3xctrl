
from abc import ABC, abstractmethod

import pygame
from pygame import Surface, event

from v3xctrl_ui.colors import WHITE
from v3xctrl_ui.fonts import MAIN_FONT, TEXT_FONT


class Tab(ABC):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int):
        self.settings = settings
        self.width = width
        self.height = height
        self.padding = padding
        self.y_offset = y_offset

        self.y_offset_headline = 60
        self.y_element_padding = 10
        self.y_section_padding = 25
        self.y_note_padding = 10

    def _draw_headline(self, surface: Surface, title: str, y: int):
        text_surface, _ = MAIN_FONT.render(title, WHITE)
        surface.blit(text_surface, (self.padding, y))
        pygame.draw.line(surface, WHITE,
                         (self.padding, y + 40),
                         (self.width - self.padding, y + 40), 2)

        return y + 40

    def _draw_note(self, surface: Surface, text: str, y: int) -> int:
        note_surface, note_rect = TEXT_FONT.render(text, WHITE)
        note_rect.topleft = (self.padding, y)
        surface.blit(note_surface, note_rect)

        return y + note_rect.height

    def handle_event(self, event: event.Event):
        for element in self.elements:
            element.handle_event(event)

    @abstractmethod
    def get_settings(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def draw(self, surface: Surface):
        raise NotImplementedError
