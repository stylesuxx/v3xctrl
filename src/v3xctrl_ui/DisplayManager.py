"""Display management for handling screen modes, sizing, and scaling."""
import logging
from typing import TYPE_CHECKING, Tuple

import pygame

if TYPE_CHECKING:
    from v3xctrl_ui.ApplicationModel import ApplicationModel


class DisplayManager:
    """Manages display configuration, fullscreen modes, and scaling calculations."""

    def __init__(
        self,
        model: 'ApplicationModel',
        base_size: Tuple[int, int],
        title: str
    ):
        """Initialize display manager.

        Args:
            model: Application model to track fullscreen state and scale
            base_size: Base resolution (width, height) for the application
            title: Window title
        """
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
        """Create the initial pygame screen based on current model state.

        Returns:
            The pygame Surface representing the screen
        """
        pygame.display.set_caption(self.title)

        if self.model.fullscreen:
            return self._create_fullscreen()
        else:
            return self._create_windowed()

    def _create_windowed(self) -> pygame.Surface:
        """Create a windowed mode screen.

        Returns:
            The pygame Surface in windowed mode
        """
        flags = pygame.DOUBLEBUF | pygame.SCALED
        self.model.scale = 1.0
        return pygame.display.set_mode(self.base_size, flags)

    def _create_fullscreen(self) -> pygame.Surface:
        """Create a fullscreen mode screen with proper scaling.

        Returns:
            The pygame Surface in fullscreen mode
        """
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
        """Toggle between fullscreen and windowed mode."""
        self.model.fullscreen = not self.model.fullscreen
        self.update_screen_mode()

    def set_fullscreen(self, fullscreen: bool) -> None:
        """Set fullscreen mode explicitly.

        Args:
            fullscreen: True for fullscreen, False for windowed
        """
        if self.model.fullscreen != fullscreen:
            self.model.fullscreen = fullscreen
            self.update_screen_mode()

    def update_screen_mode(self) -> None:
        """Update the screen to match the current fullscreen state in the model."""
        if self.model.fullscreen:
            self.screen = self._create_fullscreen()
        else:
            self.screen = self._create_windowed()

    def get_screen(self) -> pygame.Surface:
        """Get the current pygame screen surface.

        Returns:
            The current pygame Surface
        """
        return self.screen

    def get_size(self) -> Tuple[int, int]:
        """Get the current screen size.

        Returns:
            Tuple of (width, height) for the current screen
        """
        return self.screen.get_size()

    def get_base_size(self) -> Tuple[int, int]:
        """Get the base resolution (non-scaled).

        Returns:
            Tuple of (width, height) for the base resolution
        """
        return self.base_size

    def get_scale(self) -> float:
        """Get the current scale factor.

        Returns:
            Current scale factor from the model
        """
        return self.model.scale
