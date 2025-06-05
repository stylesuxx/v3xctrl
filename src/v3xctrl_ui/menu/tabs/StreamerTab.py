from pygame import Surface

from .Tab import Tab


class StreamerTab(Tab):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int):
        super().__init__(settings, width, height, padding, y_offset)

        self.elements = []

    def _draw_actions_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        self._draw_headline(surface, "Actions", y)

        y += self.y_offset_headline

        return y

    def draw(self, surface: Surface):
        _ = self._draw_actions_section(surface, 0)

    def get_settings(self) -> dict:
        return {}
