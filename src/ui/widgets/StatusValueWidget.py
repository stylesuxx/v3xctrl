from pygame import Surface

from ui.colors import BLACK
from ui.fonts import SMALL_MONO_FONT
from ui.widgets.StatusWidget import StatusWidget


class StatusValueWidget(StatusWidget):
    def __init__(self, position, size, label, padding=8):
        super().__init__(position, size, label, padding)
        self.value = None

    def set_value(self, value: int):
        self.value = value

    def draw_extra(self, surface: Surface):
        if self.value is not None:
            value_surface, _ = SMALL_MONO_FONT.render(str(self.value), BLACK)
            value_rect = value_surface.get_rect(center=self.square_rect.center)
            surface.blit(value_surface, value_rect)
