import pygame
from pygame.freetype import Font
from importlib.resources import files

pygame.init()
pygame.freetype.init()

base_path = files("v3xctrl_ui.assets.fonts")

font_path = base_path / "RussoOne-Regular.ttf"
SMALL_MONO_FONT = Font(str(font_path), 12)
BOLD_MONO_FONT = Font(str(font_path), 15)
BOLD_MONO_FONT_24 = Font(str(font_path), 24)
BOLD_MONO_FONT_32 = Font(str(font_path), 32)

font_path = base_path / "Roboto-Bold.ttf"
MAIN_FONT = Font(str(font_path), 30)
LABEL_FONT = Font(str(font_path), 20)
TEXT_FONT = Font(str(font_path), 16)

font_path = base_path / "ShareTechMono-Regular.ttf"
MONO_FONT = Font(str(font_path), 20)
