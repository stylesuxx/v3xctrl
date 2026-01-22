
from abc import ABC, abstractmethod

from pygame import Surface, event
from typing import Dict, List, Any

from v3xctrl_ui.utils.colors import WHITE
from v3xctrl_ui.utils.fonts import TEXT_FONT
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.menu.tabs.Headline import Headline


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
        self.headlines: Dict[str, Headline] = {}

    def handle_event(self, event: event.Event) -> None:
        for element in self.elements:
            element.handle_event(event)

    def update_dimensions(self, width: int, height: int) -> None:
        """
        Update tab dimensions and regenerate content.
        Called when window is resized (e.g., fullscreen toggle).
        """
        self.width = width
        self.height = height
        self._regenerate()

    def _regenerate(self) -> None:
        """Regenerate all dynamic content (headlines, layouts, etc.) with current dimensions"""
        for headline in self.headlines.values():
            headline.render(self.width, self.padding)

    def refresh_from_settings(self) -> None:
        """
        Refresh widget values from current settings.
        Called when menu is shown to ensure widgets reflect external changes (e.g., F11 fullscreen toggle).
        Override this method in subclasses to update widget states.
        """
        pass

    @abstractmethod
    def get_settings(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def draw(self, surface: Surface) -> None:
        pass

    def _add_headline(self, key: str, title: str, draw_top_line: bool = False) -> None:
        """Add a headline that will be automatically rendered and regenerated"""
        headline = Headline(title, draw_top_line)
        headline.render(self.width, self.padding)
        self.headlines[key] = headline

    def _draw_headline(
        self,
        surface: Surface,
        headline_key: str,
        y: int
    ) -> int:
        if headline_key not in self.headlines:
            raise KeyError(f"Headline '{headline_key}' not found. Did you forget to add it with _add_headline()?")

        headline = self.headlines[headline_key]
        surface.blit(headline.get_surface(), (self.padding, y))

        return headline.height

    def _draw_note(self, surface: Surface, text: str, y: int) -> int:
        note_surface, note_rect = TEXT_FONT.render(text, WHITE)
        note_rect.topleft = (self.padding, y)
        surface.blit(note_surface, note_rect)

        return y + note_rect.height
