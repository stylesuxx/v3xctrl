"""
Abstract Base class for all widgets.
"""
from abc import ABC, abstractmethod
from typing import Tuple
from pygame import Surface


class Widget(ABC):
    def __init__(self) -> None:
        # For type-hinting
        self.position: Tuple[int, int] = (0, 0)
        self.width: int = 0
        self.height: int = 0

    @abstractmethod
    def draw(self, screen: Surface) -> None:
        pass
