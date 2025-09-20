# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import Mock

import pygame

from v3xctrl_ui.menu.input.BaseWidget import BaseWidget


class ConcreteWidget(BaseWidget):
    def __init__(self, width=100, height=50):
        super().__init__()
        self._width = width
        self._height = height

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            return True

        return False

    def _draw(self, surface):
        pygame.draw.rect(
            surface,
            (255, 0, 0),
            (self.x, self.y, self._width, self._height)
        )

    def get_size(self):
        return (self._width, self._height)


class IncompleteWidget(BaseWidget):
    pass


class TestBaseWidget(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.surface = pygame.Surface((800, 600))

    def test_cannot_instantiate_abstract_base_class(self):
        with self.assertRaises(TypeError):
            BaseWidget()

    def test_cannot_instantiate_incomplete_implementation(self):
        with self.assertRaises(TypeError):
            IncompleteWidget()

    def test_concrete_widget_can_be_instantiated(self):
        widget = ConcreteWidget()
        self.assertIsInstance(widget, BaseWidget)
        self.assertIsInstance(widget, ConcreteWidget)

    def test_initial_position_is_zero(self):
        widget = ConcreteWidget()
        self.assertEqual(widget.x, 0)
        self.assertEqual(widget.y, 0)
        self.assertEqual(widget.position, (0, 0))

    def test_initial_visibility_is_true(self):
        widget = ConcreteWidget()
        self.assertTrue(widget.visible)

    def test_set_position(self):
        widget = ConcreteWidget()
        widget.set_position(10, 20)

        self.assertEqual(widget.x, 10)
        self.assertEqual(widget.y, 20)
        self.assertEqual(widget.position, (10, 20))

    def test_position_property(self):
        widget = ConcreteWidget()
        widget.x = 5
        widget.y = 15

        self.assertEqual(widget.position, (5, 15))

    def test_size_properties(self):
        widget = ConcreteWidget(width=120, height=80)

        self.assertEqual(widget.width, 120)
        self.assertEqual(widget.height, 80)
        self.assertEqual(widget.get_size(), (120, 80))

    def test_handle_event_returns_boolean(self):
        widget = ConcreteWidget()

        keydown_event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_a})
        self.assertTrue(widget.handle_event(keydown_event))

        keyup_event = pygame.event.Event(pygame.KEYUP, {'key': pygame.K_a})
        self.assertFalse(widget.handle_event(keyup_event))

    def test_draw_when_visible(self):
        widget = ConcreteWidget()
        widget._draw = Mock()

        widget.visible = True
        widget.draw(self.surface)

        widget._draw.assert_called_once_with(self.surface)

    def test_draw_when_not_visible(self):
        widget = ConcreteWidget()
        widget._draw = Mock()

        widget.visible = False
        widget.draw(self.surface)

        widget._draw.assert_not_called()

    def test_visibility_toggle(self):
        widget = ConcreteWidget()
        widget._draw = Mock()

        widget.visible = True
        widget.draw(self.surface)
        self.assertEqual(widget._draw.call_count, 1)

        widget.visible = False
        widget.draw(self.surface)
        self.assertEqual(widget._draw.call_count, 1)

        widget.visible = True
        widget.draw(self.surface)
        self.assertEqual(widget._draw.call_count, 2)

    def test_abstract_methods_signature(self):
        widget = ConcreteWidget()

        self.assertTrue(hasattr(widget, 'handle_event'))
        self.assertTrue(hasattr(widget, '_draw'))
        self.assertTrue(hasattr(widget, 'get_size'))

        self.assertTrue(callable(widget.handle_event))
        self.assertTrue(callable(widget._draw))
        self.assertTrue(callable(widget.get_size))


if __name__ == '__main__':
    unittest.main()