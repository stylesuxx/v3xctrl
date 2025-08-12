import unittest
from unittest.mock import Mock
import pygame

from v3xctrl_ui.menu.input.BaseWidget import BaseWidget  # Adjust import path as needed


class ConcreteWidget(BaseWidget):
    """Test implementation of BaseWidget"""

    def __init__(self, width=100, height=50):
        super().__init__()
        self._width = width
        self._height = height

    def handle_event(self, event):
        # Simple implementation for testing
        if event.type == pygame.KEYDOWN:
            return True
        return False

    def _draw(self, surface):
        # Simple implementation for testing
        pygame.draw.rect(surface, (255, 0, 0), (self.x, self.y, self._width, self._height))

    def get_size(self):
        return (self._width, self._height)


class IncompleteWidget(BaseWidget):
    """Widget missing abstract method implementations"""
    pass


class TestBaseWidget(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.surface = pygame.Surface((800, 600))

    def tearDown(self):
        pygame.quit()

    def test_cannot_instantiate_abstract_base_class(self):
        """Test that BaseWidget cannot be instantiated directly"""
        with self.assertRaises(TypeError):
            BaseWidget()

    def test_cannot_instantiate_incomplete_implementation(self):
        """Test that incomplete implementations cannot be instantiated"""
        with self.assertRaises(TypeError):
            IncompleteWidget()

    def test_concrete_widget_can_be_instantiated(self):
        """Test that complete implementation can be instantiated"""
        widget = ConcreteWidget()
        self.assertIsInstance(widget, BaseWidget)
        self.assertIsInstance(widget, ConcreteWidget)

    def test_initial_position_is_zero(self):
        """Test that widgets start at position (0, 0)"""
        widget = ConcreteWidget()
        self.assertEqual(widget.x, 0)
        self.assertEqual(widget.y, 0)
        self.assertEqual(widget.position, (0, 0))

    def test_initial_visibility_is_true(self):
        """Test that widgets start visible"""
        widget = ConcreteWidget()
        self.assertTrue(widget.visible)

    def test_set_position(self):
        """Test setting widget position"""
        widget = ConcreteWidget()
        widget.set_position(10, 20)
        self.assertEqual(widget.x, 10)
        self.assertEqual(widget.y, 20)
        self.assertEqual(widget.position, (10, 20))

    def test_position_property(self):
        """Test position property returns correct tuple"""
        widget = ConcreteWidget()
        widget.x = 5
        widget.y = 15
        self.assertEqual(widget.position, (5, 15))

    def test_size_properties(self):
        """Test width and height properties"""
        widget = ConcreteWidget(width=120, height=80)
        self.assertEqual(widget.width, 120)
        self.assertEqual(widget.height, 80)
        self.assertEqual(widget.get_size(), (120, 80))

    def test_handle_event_returns_boolean(self):
        """Test that handle_event returns boolean values"""
        widget = ConcreteWidget()

        keydown_event = Mock()
        keydown_event.type = pygame.KEYDOWN
        result = widget.handle_event(keydown_event)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

        keyup_event = Mock()
        keyup_event.type = pygame.KEYUP
        result = widget.handle_event(keyup_event)
        self.assertIsInstance(result, bool)
        self.assertFalse(result)

    def test_draw_when_visible(self):
        """Test that _draw is called when widget is visible"""
        widget = ConcreteWidget()
        widget._draw = Mock()

        widget.visible = True
        widget.draw(self.surface)

        widget._draw.assert_called_once_with(self.surface)

    def test_draw_when_not_visible(self):
        """Test that _draw is not called when widget is not visible"""
        widget = ConcreteWidget()
        widget._draw = Mock()

        widget.visible = False
        widget.draw(self.surface)

        widget._draw.assert_not_called()

    def test_visibility_toggle(self):
        """Test toggling visibility affects drawing behavior"""
        widget = ConcreteWidget()
        widget._draw = Mock()

        # Initially visible
        widget.visible = True
        widget.draw(self.surface)
        self.assertEqual(widget._draw.call_count, 1)

        # Hide widget
        widget.visible = False
        widget.draw(self.surface)
        # Should still be 1, not called again
        self.assertEqual(widget._draw.call_count, 1)

        # Show widget again
        widget.visible = True
        widget.draw(self.surface)
        # Should now be 2
        self.assertEqual(widget._draw.call_count, 2)

    def test_abstract_methods_signature(self):
        """Test that abstract methods have correct signatures"""
        # This ensures the abstract methods exist and have expected signatures
        widget = ConcreteWidget()

        # These should not raise AttributeError
        self.assertTrue(hasattr(widget, 'handle_event'))
        self.assertTrue(hasattr(widget, '_draw'))
        self.assertTrue(hasattr(widget, 'get_size'))

        # Test that they're callable
        self.assertTrue(callable(widget.handle_event))
        self.assertTrue(callable(widget._draw))
        self.assertTrue(callable(widget.get_size))


if __name__ == '__main__':
    unittest.main()
