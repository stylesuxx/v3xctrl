"""Display management for handling screen modes, sizing, and scaling."""
from typing import TYPE_CHECKING, Tuple
import logging
import sys
from pathlib import Path

import pygame

if TYPE_CHECKING:
    from v3xctrl_ui.core.ApplicationModel import ApplicationModel


class DisplayController:
    def __init__(
        self,
        model: 'ApplicationModel',
        base_size: Tuple[int, int],
        title: str
    ):
        self.model = model
        self.base_size = base_size
        self.title = title

        # Initialize pygame if not already initialized
        if not pygame.get_init():
            pygame.init()

        self.screen: pygame.Surface = self._create_initial_screen()

        # Setup clipboard (needs to happen after display init)
        pygame.scrap.init()
        pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)

        # Repeat keydown events when button is held
        pygame.key.set_repeat(400, 40)

    def _create_initial_screen(self) -> pygame.Surface:
        pygame.display.set_caption(self.title)

        try:
            # Get path to icon, works for both dev and PyInstaller
            if getattr(sys, 'frozen', False):
                # Running in PyInstaller bundle
                base_path = Path(sys._MEIPASS)
            else:
                # Running in normal Python environment
                base_path = Path(__file__).parent.parent

            icon_path = base_path / "assets" / "images" / "logo.png"
            icon = pygame.image.load(str(icon_path))
            pygame.display.set_icon(icon)
        except Exception as e:
            logging.info(f"Failed setting icon: {e}")

        if self.model.fullscreen:
            return self._create_fullscreen()
        else:
            return self._create_windowed()

    def _create_windowed(self) -> pygame.Surface:
        flags = pygame.DOUBLEBUF | pygame.SCALED
        self.model.scale = 1.0
        return pygame.display.set_mode(self.base_size, flags)

    def _create_fullscreen(self) -> pygame.Surface:
        # SCALED is important here, this makes it a resizable, borderless
        # window instead of "just" the legacy FULLSCREEN mode which causes
        # a bunch of complications.
        flags = pygame.DOUBLEBUF | pygame.FULLSCREEN | pygame.SCALED

        # Get biggest resolution for the active display
        modes = pygame.display.list_modes()
        size = modes[0]
        width, height = size

        # Calculate scale factor to maintain aspect ratio
        scale_x = width / self.base_size[0]
        scale_y = height / self.base_size[1]
        self.model.scale = min(scale_x, scale_y)

        return pygame.display.set_mode(size, flags)

    def toggle_fullscreen(self) -> None:
        self.model.fullscreen = not self.model.fullscreen
        self.update_screen_mode()

    def set_fullscreen(self, fullscreen: bool) -> None:
        if self.model.fullscreen != fullscreen:
            self.model.fullscreen = fullscreen
            self.update_screen_mode()

    def update_screen_mode(self) -> None:
        if self.model.fullscreen:
            self.screen = self._create_fullscreen()
        else:
            self.screen = self._create_windowed()

    def get_screen(self) -> pygame.Surface:
        return self.screen

    def get_size(self) -> Tuple[int, int]:
        return self.screen.get_size()

    def get_base_size(self) -> Tuple[int, int]:
        return self.base_size

    def get_scale(self) -> float:
        return self.model.scale
