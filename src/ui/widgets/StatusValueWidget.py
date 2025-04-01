from pygame import font, Surface
from ui.colors import BLACK
from ui.widgets.StatusWidget import StatusWidget


class StatusValueWidget(StatusWidget):
    def __init__(self, position, size, label, padding=8):
        super().__init__(position, size, label, padding)
        self.value = None

        font_size = 14
        self.value_font = font.SysFont("monospace", font_size, bold=True)

    def set_value(self, value: int):
        self.value = value

    def draw_extra(self, surface: Surface):
        if self.value is not None:
            value_surface = self.value_font.render(str(self.value), True, BLACK)
            value_rect = value_surface.get_rect(center=self.square_rect.center)
            surface.blit(value_surface, value_rect)
