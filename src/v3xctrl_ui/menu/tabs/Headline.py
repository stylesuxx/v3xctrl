import pygame
from pygame import Surface

from v3xctrl_ui.utils.colors import WHITE
from v3xctrl_ui.utils.fonts import MAIN_FONT


class Headline:
    """Encapsulates headline rendering with automatic regeneration on width changes"""

    def __init__(self, title: str, draw_top_line: bool = False):
        self.title = title
        self.draw_top_line = draw_top_line
        self.surface: Surface | None = None

    def render(self, width: int, padding: int) -> Surface:
        """Render the headline surface with the given width"""
        line_padding = 10
        line_width = 2

        text_surface, _ = MAIN_FONT.render(self.title, WHITE)
        height = text_surface.get_height()

        # Calculate total height needed
        line_padding_top = line_padding + line_width if self.draw_top_line else 0
        line_padding_bottom = line_width + line_padding
        total_height = line_padding_top + height + line_padding_bottom + 10  # 10 = y_element_padding

        # Create surface for the entire headline (text + lines)
        headline_width = width - (2 * padding)
        surface = Surface((headline_width, total_height), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))

        # Draw top line if needed
        y_offset = 0
        if self.draw_top_line:
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

        self.surface = surface
        return surface

    def get_surface(self) -> Surface:
        """Get the cached surface"""
        if self.surface is None:
            raise RuntimeError("Headline has not been rendered yet. Call render() first.")
        return self.surface

    @property
    def height(self) -> int:
        """Get the height of the rendered headline"""
        return self.surface.get_height() if self.surface else 0
