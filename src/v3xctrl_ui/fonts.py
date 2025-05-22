import pygame
from pygame.freetype import SysFont

pygame.init()

MAIN_FONT = SysFont("Arial", 30)
LABEL_FONT = SysFont("Arial", 20)
TEXT_FONT = SysFont("Arial", 16)

MONO_FONT = SysFont("couriernew", 20)

SMALL_MONO_FONT = SysFont("couriernew", 14)
BOLD_MONO_FONT = SysFont("couriernew", 16, bold=True)

BOLD_24_MONO_FONT = SysFont("couriernew", 24, bold=True)
BOLD_32_MONO_FONT = SysFont("couriernew", 32, bold=True)
