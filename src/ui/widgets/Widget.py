"""
Abstract Base class for all widgets.
"""
from abc import ABC, abstractmethod


class Widget(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def draw(self):
        raise NotImplementedError("Subclasses must implement draw method")
