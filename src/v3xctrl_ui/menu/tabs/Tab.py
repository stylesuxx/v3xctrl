
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

        self.y_offset_headline = 55
        self.y_element_padding = 10
        self.y_section_padding = 25
        self.y_note_padding = 14
        self.y_note_padding_bottom = 5

    def _draw_headline(self, surface: Surface, title: str, y: int, draw_top_line: bool = False):
        line_padding = 10
        line_width = 2

        text_surface, _ = MAIN_FONT.render(title, WHITE)
        surface.blit(text_surface, (self.padding, y))
        height = text_surface.get_height()

        line_padding_top = y - line_padding - line_width
        line_padding_bottom = y + height + line_padding

        if draw_top_line:
            pygame.draw.line(
                surface, WHITE,
                (self.padding, line_padding_top),
                (self.width - self.padding, line_padding_top), line_width
            )

        pygame.draw.line(
            surface, WHITE,
            (self.padding, line_padding_bottom),
            (self.width - self.padding, line_padding_bottom), line_width
        )

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
