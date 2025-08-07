"""
Abstract Base class for all widgets.
"""
from abc import ABC, abstractmethod
from pygame import Surface


class Widget(ABC):
    def __init__(self) -> None:
        # Subclass must set these before calling super().__init__()
        assert hasattr(self, 'width'), "Widget subclass must define self.width"
        assert hasattr(self, 'height'), "Widget subclass must define self.height"

    @abstractmethod
    def draw(self, screen: Surface) -> None:
        raise NotImplementedError("Subclasses must implement draw method")
