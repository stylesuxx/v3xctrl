"""Tests for BaseWidget."""
import os
import unittest
import pygame

# Set SDL to use dummy video driver
os.environ['SDL_VIDEODRIVER'] = 'dummy'

from v3xctrl_ui.menu.input.BaseWidget import BaseWidget


class ConcreteWidget(BaseWidget):
    """Concrete implementation for testing BaseWidget."""

    def __init__(self):
        super().__init__()
        self.draw_called = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Concrete implementation."""
        return False

    def get_size(self) -> tuple[int, int]:
        """Concrete implementation."""
        return (100, 50)

    def _draw(self, surface: pygame.Surface) -> None:
        """Concrete implementation."""
        self.draw_called = True


class TestBaseWidget(unittest.TestCase):
    """Test BaseWidget base class functionality."""

    @classmethod
    def setUpClass(cls):
        """Initialize pygame once for all tests."""
        pygame.init()
        pygame.display.set_mode((800, 600))

    def setUp(self):
        """Set up test fixtures."""
        self.widget = ConcreteWidget()

    def test_initialization(self):
        """Test widget initializes with correct defaults."""
        assert self.widget.x == 0
        assert self.widget.y == 0
        assert self.widget.visible is True
        assert self.widget.focused is False
        assert self.widget.disabled is False

    def test_set_position(self):
        """Test set_position updates coordinates."""
        self.widget.set_position(100, 200)
        assert self.widget.x == 100
        assert self.widget.y == 200

    def test_position_property(self):
        """Test position property returns tuple."""
        self.widget.set_position(50, 75)
        assert self.widget.position == (50, 75)

    def test_width_property(self):
        """Test width property calls get_size."""
        assert self.widget.width == 100

    def test_height_property(self):
        """Test height property calls get_size."""
        assert self.widget.height == 50

    def test_disable(self):
        """Test disable sets disabled to True."""
        self.widget.disable()
        assert self.widget.disabled is True

    def test_enable(self):
        """Test enable sets disabled to False."""
        self.widget.disabled = True
        self.widget.enable()
        assert self.widget.disabled is False

    def test_draw_when_visible(self):
        """Test draw calls _draw when visible."""
        surface = pygame.Surface((100, 100))
        self.widget.draw(surface)
        assert self.widget.draw_called is True

    def test_draw_when_not_visible(self):
        """Test draw skips _draw when not visible."""
        surface = pygame.Surface((100, 100))
        self.widget.visible = False
        self.widget.draw(surface)
        assert self.widget.draw_called is False


if __name__ == '__main__':
    unittest.main()
