import pygame
from pygame.freetype import Font

from .BaseInput import BaseInput


class NumberInput(BaseInput):
    def __init__(self,
                 label: str,
                 label_width: int,
                 input_width: int,
                 min_val: int,
                 max_val: int,
                 font: Font,
                 mono_font: Font,
                 on_change=None,
                 input_padding: int = 10):
        super().__init__(label, label_width, input_width, font, mono_font, on_change, input_padding)
        self.min_val = min_val
        self.max_val = max_val

    def _handle_keydown(self, event):
        super()._handle_keydown(event)

        if event.key == pygame.K_UP:
            if self.value.isdigit():
                new_val = min(self.max_val, int(self.value or 0) + 1)
                self.value = str(new_val)
                self.cursor_pos = len(self.value)
                if self.on_change:
                    self.on_change(self.value)
        elif event.key == pygame.K_DOWN:
            if self.value.isdigit():
                new_val = max(self.min_val, int(self.value or 0) - 1)
                self.value = str(new_val)
                self.cursor_pos = len(self.value)
                if self.on_change:
                    self.on_change(self.value)
        elif event.unicode.isdigit() and len(self.value) < 5:
            try:
                new_val = self.value[:self.cursor_pos] + event.unicode + self.value[self.cursor_pos:]
                if self.min_val <= int(new_val) <= self.max_val:
                    self.value = new_val
                    self.cursor_pos += 1
                    if self.on_change:
                        self.on_change(self.value)
            except ValueError:
                pass

    def get_value(self) -> int:
        try:
            return int(self.value)
        except ValueError:
            return self.min_val
