import pygame
from pygame.freetype import Font

from v3xctrl_ui.utils.resources import get_resource_path

pygame.init()
pygame.freetype.init()


def font_point_size(font: Font) -> int:
    """The font's character size as a single number.

    A freetype font can be sized separately in x and y, which is why
    `Font.size` is a float or a pair. Every font here is created with one
    size, and the y component is the one layouts measure against.
    """
    size = font.size
    if isinstance(size, tuple):
        return int(size[1])

    return int(size)


def _load_font(filename: str, size: int) -> Font:
    font_path = get_resource_path(f"assets/fonts/{filename}")
    return Font(str(font_path), size)


# RussoOne fonts
SMALL_MONO_FONT = _load_font("RussoOne-Regular.ttf", 12)
BOLD_MONO_FONT = _load_font("RussoOne-Regular.ttf", 15)
BOLD_MONO_FONT_14 = _load_font("RussoOne-Regular.ttf", 14)
BOLD_MONO_FONT_24 = _load_font("RussoOne-Regular.ttf", 24)
BOLD_MONO_FONT_32 = _load_font("RussoOne-Regular.ttf", 32)
BOLD_MONO_FONT_48 = _load_font("RussoOne-Regular.ttf", 48)

# Roboto fonts
MAIN_FONT = _load_font("Roboto-Bold.ttf", 30)
LABEL_FONT = _load_font("Roboto-Bold.ttf", 20)
TEXT_FONT = _load_font("Roboto-Bold.ttf", 16)

# ShareTech font
MONO_FONT = _load_font("ShareTechMono-Regular.ttf", 20)
