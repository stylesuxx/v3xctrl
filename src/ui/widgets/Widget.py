"""
Abstract Base class for all widgets.
"""
from abc import ABC, abstractmethod
from pygame import Surface


class Widget(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def draw(self, screen: Surface):
        raise NotImplementedError("Subclasses must implement draw method")
