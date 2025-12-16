from typing import List

from pygame import Surface

from v3xctrl_ui.menu.input import BaseWidget


class VerticalLayout:
    def __init__(self, padding_x: int = 20, element_padding: int = 10):
        self.padding_x = padding_x
        self.element_padding = element_padding
        self.widgets: List[BaseWidget] = []

    def add(self, widget: BaseWidget) -> None:
        self.widgets.append(widget)

    def draw(self, surface: Surface, y: int = 0) -> int:
        for widget in self.widgets:
            widget.set_position(self.padding_x, y)
            widget.draw(surface)
            y += widget.get_size()[1] + self.element_padding

        return y
