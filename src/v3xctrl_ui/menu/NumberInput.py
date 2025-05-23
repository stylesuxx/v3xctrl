import pygame
from pygame import Surface
from pygame.freetype import Font

from v3xctrl_ui.menu.BaseWidget import BaseWidget


class NumberInput(BaseWidget):
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
        super().__init__()

        self.label_width = label_width
        self.input_width = input_width
        self.min_val = min_val
        self.max_val = max_val
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
        self.input_rect = pygame.Rect(
            self.x + self.label_width + self.input_padding,
            self.y,
            self.input_width,
            self.input_height
        )

        # Pre-rendered input background with 3D indented effect
        self.input_surface = pygame.Surface((self.input_width, self.input_height))
        self.input_surface.fill(self.INPUT_BG_COLOR)

        # 3D border (sunken style)
        pygame.draw.line(self.input_surface, self.BORDER_LIGHT_COLOR, (0, 0), (self.input_width - 1, 0))  # top
        pygame.draw.line(self.input_surface, self.BORDER_LIGHT_COLOR, (0, 0), (0, self.input_height - 1))  # left
        pygame.draw.line(self.input_surface, self.BORDER_DARK_COLOR, (0, self.input_height - 1), (self.input_width - 1, self.input_height - 1))  # bottom
        pygame.draw.line(self.input_surface, self.BORDER_DARK_COLOR, (self.input_width - 1, 0), (self.input_width - 1, self.input_height - 1))  # right

        # Calculate cursor height and vertical position
        self.cursor_height = self.font.size
        self.cursor_y_start = self.input_rect.y + (self.input_rect.height - self.cursor_height) // 2
        self.cursor_y_end = self.cursor_y_start + self.cursor_height

        # Create Label surface - it does not change
        self.label_surface, self.label_rect = self.font.render(label, self.LABEL_COLOR)

    def set_position(self, x: int, y: int):
        super().set_position(x, y)

        self.input_rect.x = self.x + self.label_width + self.input_padding
        self.input_rect.y = self.y

        self.label_rect.x = self.x
        self.label_rect.y = self.input_rect.centery - self.label_rect.height // 2

        self.cursor_y_start = self.input_rect.y + (self.input_rect.height - self.cursor_height) // 2
        self.cursor_y_end = self.cursor_y_start + self.cursor_height

    def get_size(self) -> tuple[int, int]:
        width = self.label_width + self.input_padding + self.input_width
        height = self.input_rect.height
        return width, height

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and self.focused:
            if event.key == pygame.K_BACKSPACE and self.cursor_pos > 0:
                self.value = self.value[:self.cursor_pos - 1] + self.value[self.cursor_pos:]
                self.cursor_pos -= 1
            elif event.key == pygame.K_LEFT:
                self.cursor_pos = max(0, self.cursor_pos - 1)
            elif event.key == pygame.K_RIGHT:
                self.cursor_pos = min(len(self.value), self.cursor_pos + 1)
            elif event.key == pygame.K_UP:
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

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse(event.pos)

    def draw(self, surface: Surface):
        text_surface, text_rect = self.mono_font.render(self.value, self.TEXT_COLOR)
        text_rect.right = self.input_rect.right - self.input_padding
        text_rect.centery = self.input_rect.centery

        # Draw label and input field (with value)
        surface.blit(self.label_surface, self.label_rect.topleft)
        surface.blit(self.input_surface, self.input_rect.topleft)
        surface.blit(text_surface, text_rect)

        self._update_cursor_blink()
        if self.focused and self.cursor_visible:
            text_width = self.mono_font.get_rect(self.value[self.cursor_pos:]).width
            gap = self.CURSOR_GAP if self.cursor_pos < len(self.value) else 0
            cursor_x = text_rect.right - text_width - gap
            pygame.draw.line(surface,
                             self.CURSOR_COLOR,
                             (cursor_x, self.cursor_y_start),
                             (cursor_x, self.cursor_y_end),
                             self.CURSOR_WIDTH)

    def _handle_mouse(self, mouse_pos):
        self.focused = self.input_rect.collidepoint(mouse_pos)
        if self.focused:
            # Get pixel width of full text to right-align
            text_x = self._get_text_x()
            rel_x = mouse_pos[0] - text_x - 10

            # Determine which character was clicked
            cursor_index = len(self.value)
            for j in range(len(self.value)):
                width = self.mono_font.get_rect(self.value[:j]).width
                if width >= rel_x:
                    cursor_index = j
                    break

            self.cursor_pos = cursor_index
            self.cursor_visible = True
            self.cursor_timer = pygame.time.get_ticks()

    def _update_cursor_blink(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.cursor_timer >= self.CURSOR_INTERVAL:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = current_time

    def _get_text_x(self) -> int:
        text_width = self.mono_font.get_rect(self.value).width
        return self.input_rect.right - self.input_padding - text_width

    def get_value(self) -> int:
        try:
            return int(self.value)
        except ValueError:
            return self.min_val
