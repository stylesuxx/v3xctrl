# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame
from pygame import Surface, SRCALPHA

from v3xctrl_ui.widgets.BaseIndicatorWidget import BaseIndicatorWidget


class ConcreteIndicatorWidget(BaseIndicatorWidget):
    def draw(self, screen: Surface, value: float) -> None:
        pass


class TestBaseIndicatorWidget(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def test_initialization_default_parameters(self):
        widget = ConcreteIndicatorWidget(
            position=(10, 20),
            size=(100, 50)
        )

        self.assertEqual(widget.position, (10, 20))
        self.assertEqual(widget.width, 100)
        self.assertEqual(widget.height, 50)
        self.assertEqual(widget.range_mode, "symmetric")
        self.assertIsNone(widget.color_fn)
        self.assertEqual(widget.bg_alpha, 150)
        self.assertEqual(widget.padding, 6)

    def test_initialization_custom_parameters(self):
        def custom_color_fn(value):
            return (255, 0, 0)

        widget = ConcreteIndicatorWidget(
            position=(50, 100),
            size=(200, 80),
            range_mode="positive",
            color_fn=custom_color_fn,
            bg_alpha=200,
            padding=10
        )

        self.assertEqual(widget.position, (50, 100))
        self.assertEqual(widget.width, 200)
        self.assertEqual(widget.height, 80)
        self.assertEqual(widget.range_mode, "positive")
        self.assertEqual(widget.color_fn, custom_color_fn)
        self.assertEqual(widget.bg_alpha, 200)
        self.assertEqual(widget.padding, 10)

    def test_valid_range_modes(self):
        widget_symmetric = ConcreteIndicatorWidget(
            position=(0, 0),
            size=(100, 50),
            range_mode="symmetric"
        )
        self.assertEqual(widget_symmetric.range_mode, "symmetric")

        widget_positive = ConcreteIndicatorWidget(
            position=(0, 0),
            size=(100, 50),
            range_mode="positive"
        )
        self.assertEqual(widget_positive.range_mode, "positive")

    def test_invalid_range_mode_raises_error(self):
        with self.assertRaises(ValueError) as context:
            ConcreteIndicatorWidget(
                position=(0, 0),
                size=(100, 50),
                range_mode="invalid_mode"
            )

            self.assertIn("Invalid range_mode 'invalid_mode'", str(context.exception))
            self.assertIn("Must be one of: {'symmetric', 'positive'}", str(context.exception))

    def test_valid_range_modes_constant(self):
        self.assertEqual(BaseIndicatorWidget.VALID_RANGE_MODES, {"symmetric", "positive"})

    def test_color_function_assignment(self):
        def red_color(value):
            return (255, 0, 0)

        def green_color(value):
            return (0, 255, 0)

        widget = ConcreteIndicatorWidget(
            position=(0, 0),
            size=(100, 50),
            color_fn=red_color
        )

        self.assertEqual(widget.color_fn, red_color)
        self.assertEqual(widget.color_fn(0.5), (255, 0, 0))

        widget.color_fn = green_color
        self.assertEqual(widget.color_fn(0.5), (0, 255, 0))

    def test_draw_background(self):
        with patch('v3xctrl_ui.widgets.BaseIndicatorWidget.Surface') as mock_surface_class:
            mock_surface = MagicMock()
            mock_surface_class.return_value = mock_surface

            mock_screen = MagicMock()

            widget = ConcreteIndicatorWidget(
                position=(25, 35),
                size=(150, 75),
                bg_alpha=180
            )

            widget.draw_background(mock_screen)

            mock_surface_class.assert_called_once_with((150, 75), SRCALPHA)
            mock_surface.fill.assert_called_once_with((0, 0, 0, 180))
            mock_screen.blit.assert_called_once_with(mock_surface, (25, 35))

    def test_draw_background_different_alpha(self):
        with patch('v3xctrl_ui.widgets.BaseIndicatorWidget.Surface') as mock_surface_class:
            mock_surface = MagicMock()
            mock_surface_class.return_value = mock_surface

            mock_screen = MagicMock()

            widget = ConcreteIndicatorWidget(
                position=(0, 0),
                size=(100, 50),
                bg_alpha=100
            )

            widget.draw_background(mock_screen)

            mock_surface.fill.assert_called_once_with((0, 0, 0, 100))

    def test_abstract_draw_method(self):
        with self.assertRaises(TypeError):
            BaseIndicatorWidget(
                position=(0, 0),
                size=(100, 50)
            )

    def test_concrete_implementation_can_instantiate(self):
        widget = ConcreteIndicatorWidget(
            position=(0, 0),
            size=(100, 50)
        )

        self.assertIsInstance(widget, BaseIndicatorWidget)

        mock_screen = MagicMock()
        widget.draw(mock_screen, 0.5)

    def test_size_tuple_unpacking(self):
        widget = ConcreteIndicatorWidget(
            position=(10, 20),
            size=(300, 200)
        )

        self.assertEqual(widget.width, 300)
        self.assertEqual(widget.height, 200)

    def test_position_tuple_storage(self):
        widget = ConcreteIndicatorWidget(
            position=(15, 25),
            size=(100, 50)
        )

        self.assertEqual(widget.position, (15, 25))
        self.assertEqual(widget.position[0], 15)
        self.assertEqual(widget.position[1], 25)

    def test_zero_size_handling(self):
        widget = ConcreteIndicatorWidget(
            position=(0, 0),
            size=(0, 0)
        )

        self.assertEqual(widget.width, 0)
        self.assertEqual(widget.height, 0)

    def test_negative_size_handling(self):
        widget = ConcreteIndicatorWidget(
            position=(0, 0),
            size=(-10, -5)
        )

        self.assertEqual(widget.width, -10)
        self.assertEqual(widget.height, -5)

    def test_zero_alpha_background(self):
        with patch('v3xctrl_ui.widgets.BaseIndicatorWidget.Surface') as mock_surface_class:
            mock_surface = MagicMock()
            mock_surface_class.return_value = mock_surface

            widget = ConcreteIndicatorWidget(
                position=(0, 0),
                size=(100, 50),
                bg_alpha=0
            )

            mock_screen = MagicMock()
            widget.draw_background(mock_screen)

            mock_surface.fill.assert_called_once_with((0, 0, 0, 0))

    def test_maximum_alpha_background(self):
        with patch('v3xctrl_ui.widgets.BaseIndicatorWidget.Surface') as mock_surface_class:
            mock_surface = MagicMock()
            mock_surface_class.return_value = mock_surface

            widget = ConcreteIndicatorWidget(
                position=(0, 0),
                size=(100, 50),
                bg_alpha=255
            )

            mock_screen = MagicMock()
            widget.draw_background(mock_screen)

            mock_surface.fill.assert_called_once_with((0, 0, 0, 255))

    def test_negative_padding(self):
        widget = ConcreteIndicatorWidget(
            position=(0, 0),
            size=(100, 50),
            padding=-5
        )

        self.assertEqual(widget.padding, -5)

    def test_color_function_with_different_return_types(self):
        def tuple_color_fn(value):
            return (255, 128, 64)

        def list_color_fn(value):
            return [255, 128, 64]

        widget = ConcreteIndicatorWidget(
            position=(0, 0),
            size=(100, 50),
            color_fn=tuple_color_fn
        )

        self.assertEqual(widget.color_fn(0.5), (255, 128, 64))

        widget.color_fn = list_color_fn
        self.assertEqual(widget.color_fn(0.5), [255, 128, 64])

    def test_all_parameters_edge_cases(self):
        def edge_color_fn(value):
            return (0, 0, 0)

        widget = ConcreteIndicatorWidget(
            position=(0, 0),
            size=(1, 1),
            range_mode="positive",
            color_fn=edge_color_fn,
            bg_alpha=1,
            padding=0
        )

        self.assertEqual(widget.position, (0, 0))
        self.assertEqual(widget.width, 1)
        self.assertEqual(widget.height, 1)
        self.assertEqual(widget.range_mode, "positive")
        self.assertEqual(widget.color_fn, edge_color_fn)
        self.assertEqual(widget.bg_alpha, 1)
        self.assertEqual(widget.padding, 0)


if __name__ == '__main__':
    unittest.main()
