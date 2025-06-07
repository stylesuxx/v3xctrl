import logging
from typing import Tuple
import pygame
from pygame import display, time

from v3xctrl_control import Server

from v3xctrl_ui.Settings import Settings
from v3xctrl_ui.VideoReceiver import VideoReceiver


class Init:
    @classmethod
    def settings(self, path: str = "settings.toml") -> Settings:
        settings = Settings(path)
        settings.save()

        return settings

    @classmethod
    def server(self, port: int, handlers: dict) -> Tuple[Server, str]:
        try:
            server = Server(port)

            for type, callback in handlers.get("messages", []):
                server.subscribe(type, callback)

            for state, callback in handlers.get("states", []):
                server.on(state, callback)

            server.start()

            return server, None

        except OSError as e:
            msg = "Control port already in use" if e.errno == 98 else f"Server error: {str(e)}"
            logging.error(msg)

            return None, msg

    @classmethod
    def ui(self, size: Tuple[int, int], title: str) -> Tuple[pygame.Surface, pygame.time.Clock]:
        pygame.init()
        flags = pygame.DOUBLEBUF | pygame.SCALED
        screen = display.set_mode(size, flags)
        display.set_caption(title)
        clock = time.Clock()

        return screen, clock

    @classmethod
    def video_receiver(self, port: int, error_callback: callable) -> VideoReceiver:
        video_receiver = VideoReceiver(port, error_callback)
        video_receiver.start()

        return video_receiver
