from typing import List, Tuple, Any

import pygame
from pygame import display, time

from v3xctrl_control import Server
from v3xctrl_control.message import Message
from v3xctrl_control.State import State

from v3xctrl_ui.Settings import Settings


class Init:
    """
    Factory to help with initialization of core components
    """

    @classmethod
    def settings(cls, path: str = "settings.toml") -> Settings:
        """
        Initialize settings from a file. Create settings file in case it does
        not exist.
        """
        settings = Settings(path)
        settings.save()

        return settings

    @classmethod
    def server(
        cls,
        port: int,
        message_handlers: List[Tuple[Message, Any]],
        state_handlers: List[Tuple[State, Any]],
        udp_ttl_ms: int,
    ) -> Server:
        try:
            server = Server(port, udp_ttl_ms)

            for message_type, callback in message_handlers:
                server.subscribe(message_type, callback)

            for state, callback in state_handlers:
                server.on(state, callback)

            server.start()

            return server

        except OSError as e:
            msg = "Control port already in use" if e.errno == 98 else f"Server error: {str(e)}"
            raise RuntimeError(msg) from e

    @classmethod
    def ui(cls, size: Tuple[int, int], title: str) -> Tuple[pygame.Surface, pygame.time.Clock]:
        pygame.init()

        flags = pygame.DOUBLEBUF | pygame.SCALED
        screen = display.set_mode(size, flags)
        display.set_caption(title)
        clock = time.Clock()

        # Init clipboard (Needs to happen after display init)
        pygame.scrap.init()
        pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)

        # Repeat keydown events when button is held
        pygame.key.set_repeat(400, 40)

        return screen, clock
