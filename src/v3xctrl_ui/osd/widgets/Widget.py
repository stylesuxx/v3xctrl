"""
Abstract Base class for all widgets.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pygame import Surface

ValueT = TypeVar("ValueT")


class Widget(ABC, Generic[ValueT]):
    """One element of the OSD, drawn from a single value each frame.

    The parameter is the type of that value. A widget that renders from its
    own state binds it to None.
    """

    def __init__(self) -> None:
        # For type-hinting
        self.position: tuple[int, int] = (0, 0)
        self.width: int = 0
        self.height: int = 0

    @abstractmethod
    def draw(self, screen: Surface, value: ValueT) -> None:
        pass
