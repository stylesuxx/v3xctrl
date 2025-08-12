import pygame
from pygame.freetype import Font
from typing import Optional, Callable
from .BaseInput import BaseInput


class NumberInput(BaseInput):
    def __init__(
        self,
        label: str,
        label_width: int,
        input_width: int,
        min_val: int,
        max_val: int,
        font: Font,
        mono_font: Font,
        on_change: Optional[Callable[[str], None]] = None,
        input_padding: int = 10
    ) -> None:
        super().__init__(
            label,
            label_width,
            input_width,
            font,
            mono_font,
            on_change,
            input_padding
        )
        self.min_val = min_val
        self.max_val = max_val

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        super()._handle_keydown(event)

        if event.key == pygame.K_UP:
            if self.value.isdigit():
                new_val = str(min(self.max_val, int(self.value or 0) + 1))
                if new_val != self.value:
                    self.value = new_val
                    self.cursor_pos = len(self.value)
                    if self.on_change:
                        self.on_change(self.value)

        elif event.key == pygame.K_DOWN:
            if self.value.isdigit():
                new_val = str(max(self.min_val, int(self.value or 0) - 1))
                if new_val != self.value:
                    self.value = new_val
                    self.cursor_pos = len(self.value)
                    if self.on_change:
                        self.on_change(self.value)
        elif (
            hasattr(event, 'unicode') and
            event.unicode.isdigit() and
            len(self.value) < 5
        ):
            try:
                new_val = str(self.value[:self.cursor_pos] + event.unicode + self.value[self.cursor_pos:])
                if new_val != self.value:
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
