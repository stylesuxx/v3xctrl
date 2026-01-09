from typing import Tuple

from pygame import Surface

from v3xctrl_ui.utils.colors import WHITE, RED
from v3xctrl_ui.utils.helpers import round_corners
from v3xctrl_ui.osd.widgets.TextWidget import TextWidget


class RecWidget(TextWidget):
    """Recording indicator widget with red background and white 'REC' text."""

    def __init__(
        self,
        position: Tuple[int, int],
        top_padding: int = 5,
        bottom_padding: int = 3,
        left_padding: int = 8,
        right_padding: int = 8,
        border_radius: int = 5
    ) -> None:
        self.border_radius = border_radius

        # Calculate length based on "REC" text
        # We need to estimate the width first, TextWidget will calculate proper dimensions
        estimated_length = 50  # Will be adjusted after initialization

        super().__init__(
            position=position,
            length=estimated_length,
            top_padding=top_padding,
            bottom_padding=bottom_padding,
            left_padding=left_padding,
            right_padding=right_padding
        )

        self.set_background_color(RED, alpha=255)
        self.set_text_color(WHITE)

        _, text_rect = self.font.render("REC", WHITE)
        self.width = text_rect.width + self.left_padding + self.right_padding
        self.length = self.width

        self._create_background()

    def _create_background(self) -> None:
        super()._create_background()
        self.bg_surface = round_corners(self.bg_surface, self.border_radius)

    def draw(self, screen: Surface, _=None) -> None:
        super().draw(screen, "REC")
