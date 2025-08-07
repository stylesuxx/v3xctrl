import pygame
from pygame.freetype import Font
from typing import Optional, Callable

from .BaseInput import BaseInput


class TextInput(BaseInput):
    def __init__(
        self,
        label: str,
        label_width: int,
        input_width: int,
        font: Font,
        mono_font: Font,
        max_length: int = 32,
        on_change: Optional[Callable[[], None]] = None,
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
        self.max_length = max_length

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        super()._handle_keydown(event)

        if event.key == pygame.K_RETURN:
            if self.on_change:
                self.on_change(self.value)
        elif (
            event.unicode and
            event.unicode.isprintable() and
            len(self.value) < self.max_length
        ):
            self.value = self.value[:self.cursor_pos] + event.unicode + self.value[self.cursor_pos:]
            self.cursor_pos += 1
            if self.on_change:
                self.on_change(self.value)

    def get_value(self) -> str:
        return self.value
