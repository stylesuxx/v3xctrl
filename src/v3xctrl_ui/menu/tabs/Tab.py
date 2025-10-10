
from abc import ABC, abstractmethod

import pygame
from pygame import Surface, event
from typing import Dict, List, Any

from v3xctrl_ui.colors import WHITE
from v3xctrl_ui.fonts import MAIN_FONT, TEXT_FONT
from v3xctrl_ui.Settings import Settings


class Tab(ABC):
    def __init__(
        self,
        settings: Settings,
        width: int,
        height: int,
        padding: int,
        y_offset: int
    ) -> None:
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

        self.elements: List[Any] = []
        self.headline_surfaces: Dict[str, Surface] = {}

    def handle_event(self, event: event.Event) -> None:
        for element in self.elements:
            element.handle_event(event)

    @abstractmethod
    def get_settings(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def draw(self, surface: Surface) -> None:
        pass

    def _create_headline(
        self,
        title: str,
        draw_top_line: bool = False
      ) -> Surface:
        """
        Pre-render a headline surface (EXPENSIVE - only call once in __init__).
        Returns a surface with the headline text and lines already drawn.
        """
        line_padding = 10
        line_width = 2

        text_surface, _ = MAIN_FONT.render(title, WHITE)
        height = text_surface.get_height()

        # Calculate total height needed
        line_padding_top = line_padding + line_width if draw_top_line else 0
        line_padding_bottom = height + line_padding
        total_height = line_padding_top + height + line_padding_bottom

        # Create surface for the entire headline (text + lines)
        headline_width = self.width - (2 * self.padding)
        surface = Surface((headline_width, total_height), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))

        # Draw top line if needed
        y_offset = 0
        if draw_top_line:
            pygame.draw.line(
                surface, WHITE,
                (0, line_width // 2),
                (headline_width, line_width // 2),
                line_width
            )
            y_offset = line_padding_top

        surface.blit(text_surface, (0, y_offset))

        # Draw bottom line
        bottom_line_y = y_offset + height + line_padding
        pygame.draw.line(
            surface, WHITE,
            (0, bottom_line_y),
            (headline_width, bottom_line_y),
            line_width
        )

        return surface

    def _draw_headline(
        self,
        surface: Surface,
        headline_key: str,
        y: int
    ) -> int:
        if headline_key not in self.headline_surfaces:
            raise KeyError(f"Headline '{headline_key}' not found. Did you forget to pre-render it in __init__?")

        headline = self.headline_surfaces[headline_key]
        surface.blit(headline, (self.padding, y))

        return headline.height

    def _draw_note(self, surface: Surface, text: str, y: int) -> int:
        note_surface, note_rect = TEXT_FONT.render(text, WHITE)
        note_rect.topleft = (self.padding, y)
        surface.blit(note_surface, note_rect)

        return y + note_rect.height
