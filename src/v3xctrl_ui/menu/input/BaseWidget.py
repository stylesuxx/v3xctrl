from abc import ABC, abstractmethod
import pygame
from pygame import Surface


class BaseWidget(ABC):
    def __init__(self) -> None:
        self.x = 0
        self.y = 0

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    @abstractmethod
    def draw(self, surface: Surface) -> None:
        pass

    @abstractmethod
    def get_size(self) -> tuple[int, int]:
        pass

    def set_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    @property
    def width(self) -> int:
        return self.get_size()[0]

    @property
    def height(self) -> int:
        return self.get_size()[1]
