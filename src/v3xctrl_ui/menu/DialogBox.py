import pygame
from pygame import Surface
from pygame.freetype import SysFont, STYLE_STRONG
from typing import Callable, List

from v3xctrl_ui.menu.input.Button import Button
from v3xctrl_ui.colors import TRANSPARENT_BLACK, WHITE, DARK_GREY


class DialogBox:
    BG_COLOR = TRANSPARENT_BLACK
    BOX_COLOR = DARK_GREY
    TEXT_COLOR = WHITE
    TITLE_COLOR = WHITE

    def __init__(
        self,
        title: str,
        lines: List[str],
        button_label: str,
        on_confirm: Callable[[], None]
    ) -> None:
        self.title = title
        self.original_lines = lines
        self.wrapped_lines: List[str] = []
        self.button_label = button_label
        self.on_confirm = on_confirm
        self.visible = False

        self.font = SysFont("monospace", 20)
        self.padding = 20
        self.line_spacing = 30

        self.button: Button = Button(
            label=button_label,
            width=200,
            height=40,
            font=self.font,
            callback=self._confirm
        )

        self.surface_size = None
        self.box_rect = None

    def _confirm(self) -> None:
        self.hide()
        self.on_confirm()

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def set_text(self, lines: List[str]) -> None:
        self.original_lines = lines

    def _wrap_text(self, max_width: int) -> List[str]:
        wrapped: List[str] = []
        for line in self.original_lines:
            words = line.split()
            current = ""
            for word in words:
                test_line = f"{current} {word}".strip()
                rect = self.font.get_rect(test_line)
                if rect.width > max_width and current:
                    wrapped.append(current)
                    current = word
                else:
                    current = test_line
            if current:
                wrapped.append(current)
        return wrapped

    def draw(self, surface: Surface) -> None:
        if not self.visible:
            return

        self.surface_size = surface.get_size()
        rect = surface.get_rect()

        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill(self.BG_COLOR)
        surface.blit(overlay, (0, 0))

        box_width = rect.width // 2
        text_max_width = box_width - 2 * self.padding
        self.wrapped_lines = self._wrap_text(text_max_width)

        title_surface, _ = self.font.render(self.title, self.TITLE_COLOR, style=STYLE_STRONG)
        title_height = title_surface.get_height()

        box_height = (
            self.padding + title_height +
            self.padding + len(self.wrapped_lines) * self.line_spacing +
            self.padding + self.button.height +
            self.padding
        )

        box_x = (rect.width - box_width) // 2
        box_y = (rect.height - box_height) // 2
        self.box_rect = pygame.Rect(box_x, box_y, box_width, box_height)

        pygame.draw.rect(surface, self.BOX_COLOR, self.box_rect)

        # Draw title
        y = self.box_rect.y + self.padding
        surface.blit(title_surface, (
            self.box_rect.centerx - title_surface.get_width() // 2,
            y
        ))
        y += title_height + self.padding

        # Draw wrapped lines
        for line in self.wrapped_lines:
            text_surface, _ = self.font.render(line, self.TEXT_COLOR)
            surface.blit(text_surface, (self.box_rect.x + self.padding, y))
            y += self.line_spacing

        # Button
        y += self.padding
        self.button.set_position(
            self.box_rect.centerx - self.button.width // 2,
            y
        )
        self.button.draw(surface)

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.visible:
            return
        self.button.handle_event(event)
