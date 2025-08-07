import pygame
from pygame import Surface
from pygame.freetype import Font
from typing import Callable, Tuple, Optional

from .BaseWidget import BaseWidget


class BaseInput(BaseWidget):
    LABEL_COLOR = (220, 220, 220)
    INPUT_BG_COLOR = (255, 255, 255)
    TEXT_COLOR = (0, 0, 0)
    CURSOR_COLOR = (80, 80, 80)

    BORDER_LIGHT_COLOR = (180, 180, 180)
    BORDER_DARK_COLOR = (100, 100, 100)

    CURSOR_PADDING = 8
    CURSOR_WIDTH = 1
    CURSOR_INTERVAL = 500
    CURSOR_GAP = 2

    def __init__(
        self,
        label: str,
        label_width: int,
        input_width: int,
        font: Font,
        mono_font: Font,
        on_change: Optional[Callable[[str], None]] = None,
        input_padding: int = 10
    ) -> None:
        super().__init__()
        self.label = label
        self.label_width = label_width
        self.input_width = input_width
        self.font = font
        self.mono_font = mono_font
        self.on_change = on_change
        self.input_padding = input_padding

        self.value = ""
        self.cursor_pos = 0
        self.focused = False
        self.cursor_visible = True
        self.cursor_timer = 0

        self.input_height = self.font.size + self.input_padding
        self.input_rect = pygame.Rect(0, 0, self.input_width, self.input_height)

        self.input_surface = pygame.Surface((self.input_width, self.input_height))
        self._draw_input_background()

        self.cursor_height = self.font.size
        self.cursor_y_start = 0
        self.cursor_y_end = 0

        self.label_surface, self.label_rect = self.font.render(label, self.LABEL_COLOR)

    def _draw_input_background(self) -> None:
        self.input_surface.fill(self.INPUT_BG_COLOR)
        pygame.draw.line(self.input_surface, self.BORDER_LIGHT_COLOR, (0, 0), (self.input_width - 1, 0))
        pygame.draw.line(self.input_surface, self.BORDER_LIGHT_COLOR, (0, 0), (0, self.input_height - 1))
        pygame.draw.line(self.input_surface, self.BORDER_DARK_COLOR, (0, self.input_height - 1), (self.input_width - 1, self.input_height - 1))
        pygame.draw.line(self.input_surface, self.BORDER_DARK_COLOR, (self.input_width - 1, 0), (self.input_width - 1, self.input_height - 1))

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)
        self.input_rect.x = self.x + self.label_width + self.input_padding
        self.input_rect.y = self.y
        self.label_rect.topleft = (self.x, self.input_rect.centery - self.label_rect.height // 2)
        self.cursor_y_start = self.input_rect.y + (self.input_rect.height - self.cursor_height) // 2
        self.cursor_y_end = self.cursor_y_start + self.cursor_height

    def get_size(self) -> tuple[int, int]:
        return self.label_width + self.input_padding + self.input_width, self.input_rect.height

    def draw(self, surface: Surface) -> None:
        text_surface, text_rect = self.mono_font.render(self.value, self.TEXT_COLOR)
        text_rect.right = self.input_rect.right - self.input_padding
        text_rect.centery = self.input_rect.centery

        surface.blit(self.label_surface, self.label_rect.topleft)
        surface.blit(self.input_surface, self.input_rect.topleft)
        surface.blit(text_surface, text_rect)

        self._update_cursor_blink()
        if self.focused and self.cursor_visible:
            text_width = self.mono_font.get_rect(self.value[self.cursor_pos:]).width
            gap = self.CURSOR_GAP if self.cursor_pos < len(self.value) else 0
            cursor_x = text_rect.right - text_width - gap
            pygame.draw.line(surface, self.CURSOR_COLOR, (cursor_x, self.cursor_y_start), (cursor_x, self.cursor_y_end), self.CURSOR_WIDTH)

    def _handle_mouse(self, mouse_pos: Tuple[int, int]) -> None:
        self.focused = self.input_rect.collidepoint(mouse_pos)
        if self.focused:
            text_x = self._get_text_x()
            rel_x = mouse_pos[0] - text_x - 10
            self.cursor_pos = len(self.value)
            for j in range(len(self.value)):
                width = self.mono_font.get_rect(self.value[:j]).width
                if width >= rel_x:
                    self.cursor_pos = j
                    break
            self.cursor_visible = True
            self.cursor_timer = pygame.time.get_ticks()

    def _update_cursor_blink(self) -> None:
        current_time = pygame.time.get_ticks()
        if current_time - self.cursor_timer >= self.CURSOR_INTERVAL:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = current_time

    def _get_text_x(self) -> int:
        return self.input_rect.right - self.input_padding - self.mono_font.get_rect(self.value).width

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse(event.pos)
        elif event.type == pygame.KEYDOWN and self.focused:
            self._handle_keydown(event)

    def _get_clipboard_text(self) -> str | None:
        for type in pygame.scrap.get_types():
            if type.startswith("text/plain"):
                data = pygame.scrap.get(type)
                if data:
                    try:
                        if isinstance(data, bytes):
                            return data.decode("utf-8", errors="ignore")

                        return data.strip()
                    except UnicodeDecodeError:
                        continue
        return None

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        mods = pygame.key.get_mods()

        # Handle paste from clipboard
        if event.key == pygame.K_v and mods & pygame.KMOD_CTRL:
            if pygame.scrap.get_init():
                pasted_text = self._get_clipboard_text()
                if pasted_text:
                    self.value = pasted_text
                    self.cursor_pos = len(self.value)
                    if self.on_change:
                        self.on_change(self.value)
            return

        if event.key == pygame.K_BACKSPACE and self.cursor_pos > 0:
            self.value = self.value[:self.cursor_pos - 1] + self.value[self.cursor_pos:]
            self.cursor_pos -= 1
        elif event.key == pygame.K_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
        elif event.key == pygame.K_RIGHT:
            self.cursor_pos = min(len(self.value), self.cursor_pos + 1)

    def get_value(self) -> int | str:
        return self.value
