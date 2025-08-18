from abc import ABC, abstractmethod
import pygame
from pygame import Surface


class BaseWidget(ABC):
    def __init__(self) -> None:
        self.x = 0
        self.y = 0

        self.visible = True
        self.focused = False
        self.disabled = False

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle an event.
        Return True if event was consumed.
        """
        pass

    @abstractmethod
    def get_size(self) -> tuple[int, int]:
        pass

    def draw(self, surface: Surface) -> None:
        """Only draw if actually visible."""
        if not self.visible:
            return

        self._draw(surface)

    def set_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def disable(self) -> None:
        self.disabled = True

    def enable(self) -> None:
        self.disabled = False

    @property
    def position(self) -> tuple[int, int]:
        return (self.x, self.y)

    @property
    def width(self) -> int:
        return self.get_size()[0]

    @property
    def height(self) -> int:
        return self.get_size()[1]

    @abstractmethod
    def _draw(self, surface: Surface) -> None:
        pass
