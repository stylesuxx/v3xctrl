import pygame
from pygame.freetype import Font
import sys
import os
from pathlib import Path

pygame.init()
pygame.freetype.init()


def _get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running in normal Python environment
        base_path = Path(__file__).parent.parent
    return base_path / relative_path


def _load_font(filename: str, size: int) -> Font:
    """Load a font from the assets."""
    font_path = _get_resource_path(f"assets/fonts/{filename}")
    return Font(str(font_path), size)


# RussoOne fonts
SMALL_MONO_FONT = _load_font("RussoOne-Regular.ttf", 12)
BOLD_MONO_FONT = _load_font("RussoOne-Regular.ttf", 15)
BOLD_MONO_FONT_14 = _load_font("RussoOne-Regular.ttf", 14)
BOLD_MONO_FONT_24 = _load_font("RussoOne-Regular.ttf", 24)
BOLD_MONO_FONT_32 = _load_font("RussoOne-Regular.ttf", 32)

# Roboto fonts
MAIN_FONT = _load_font("Roboto-Bold.ttf", 30)
LABEL_FONT = _load_font("Roboto-Bold.ttf", 20)
TEXT_FONT = _load_font("Roboto-Bold.ttf", 16)

# ShareTech font
MONO_FONT = _load_font("ShareTechMono-Regular.ttf", 20)
