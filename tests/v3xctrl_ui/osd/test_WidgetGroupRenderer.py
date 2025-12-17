# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
from unittest.mock import patch

from v3xctrl_ui.osd.WidgetGroupRenderer import WidgetGroupRenderer
from v3xctrl_ui.widgets import TextWidget


class TestWidgetGroupRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.screen = pygame.Surface((800, 600), pygame.SRCALPHA)

        self.widget1 = TextWidget((0, 0), 100)
        self.widget2 = TextWidget((0, 0), 100)
        self.widget3 = TextWidget((0, 0), 100)

        self.widgets = {
            "widget1": self.widget1,
            "widget2": self.widget2,
            "widget3": self.widget3
        }.items()

        self.widget_settings = {
            "widget1": {"display": True},
            "widget2": {"display": True},
            "widget3": {"display": True}
        }

        self.get_value = lambda name: f"Value for {name}"

    def test_filter_visible_widgets_returns_all_when_all_visible(self):
        visible = WidgetGroupRenderer._filter_visible_widgets(
            self.widgets,
            self.widget_settings
        )

        self.assertEqual(len(visible), 3)
        names = [name for name, _ in visible]
        self.assertIn("widget1", names)
        self.assertIn("widget2", names)
        self.assertIn("widget3", names)

    def test_filter_visible_widgets_filters_hidden_widgets(self):
        self.widget_settings["widget2"]["display"] = False

        visible = WidgetGroupRenderer._filter_visible_widgets(
            self.widgets,
            self.widget_settings
        )

        self.assertEqual(len(visible), 2)
        names = [name for name, _ in visible]
        self.assertIn("widget1", names)
        self.assertNotIn("widget2", names)
        self.assertIn("widget3", names)

    def test_filter_visible_widgets_defaults_to_visible_when_no_settings(self):
        widget_settings = {}

        visible = WidgetGroupRenderer._filter_visible_widgets(
            self.widgets,
            widget_settings
        )

        self.assertEqual(len(visible), 3)

    def test_filter_visible_widgets_returns_empty_when_all_hidden(self):
        self.widget_settings["widget1"]["display"] = False
        self.widget_settings["widget2"]["display"] = False
        self.widget_settings["widget3"]["display"] = False

        visible = WidgetGroupRenderer._filter_visible_widgets(
            self.widgets,
            self.widget_settings
        )

        self.assertEqual(len(visible), 0)

    def test_calculate_dimensions_with_no_padding(self):
        self.widget1.width = 100
        self.widget1.height = 20
        self.widget2.width = 80
        self.widget2.height = 30
        self.widget3.width = 120
        self.widget3.height = 25

        visible = [
            ("widget1", self.widget1),
            ("widget2", self.widget2),
            ("widget3", self.widget3)
        ]

        width, height = WidgetGroupRenderer._calculate_dimensions(visible, 0)

        self.assertEqual(width, 120)
        self.assertEqual(height, 75)

    def test_calculate_dimensions_with_padding(self):
        self.widget1.width = 100
        self.widget1.height = 20
        self.widget2.width = 80
        self.widget2.height = 30

        visible = [
            ("widget1", self.widget1),
            ("widget2", self.widget2)
        ]

        width, height = WidgetGroupRenderer._calculate_dimensions(visible, 10)

        self.assertEqual(width, 100)
        self.assertEqual(height, 60)

    def test_calculate_dimensions_single_widget(self):
        self.widget1.width = 150
        self.widget1.height = 40

        visible = [("widget1", self.widget1)]

        width, height = WidgetGroupRenderer._calculate_dimensions(visible, 5)

        self.assertEqual(width, 150)
        self.assertEqual(height, 40)

    def test_calculate_dimensions_empty_list(self):
        visible = []

        width, height = WidgetGroupRenderer._calculate_dimensions(visible, 5)

        self.assertEqual(width, 0)
        self.assertEqual(height, 0)

    def test_draw_widgets_to_surface_sets_positions(self):
        self.widget1.height = 20
        self.widget2.height = 30
        self.widget3.height = 25

        surface = pygame.Surface((100, 85), pygame.SRCALPHA)
        visible = [
            ("widget1", self.widget1),
            ("widget2", self.widget2),
            ("widget3", self.widget3)
        ]

        WidgetGroupRenderer._draw_widgets_to_surface(
            surface, visible, self.get_value, 5
        )

        self.assertEqual(self.widget1.position, (0, 0))
        self.assertEqual(self.widget2.position, (0, 25))
        self.assertEqual(self.widget3.position, (0, 60))

    def test_draw_widgets_to_surface_calls_draw_with_values(self):
        surface = pygame.Surface((100, 50), pygame.SRCALPHA)
        visible = [("widget1", self.widget1)]

        with patch.object(self.widget1, 'draw') as mock_draw:
            WidgetGroupRenderer._draw_widgets_to_surface(
                surface, visible, self.get_value, 0
            )
            mock_draw.assert_called_once_with(surface, "Value for widget1")

    def test_render_group_uses_default_alignment(self):
        settings = {"display": True}

        with patch('pygame.display.get_window_size', return_value=(800, 600)):
            with patch('v3xctrl_ui.osd.WidgetGroupRenderer.calculate_widget_position') as mock_calc:
                mock_calc.return_value = (0, 0)

                WidgetGroupRenderer.render_group(
                    self.screen,
                    self.widgets,
                    settings,
                    self.widget_settings,
                    self.get_value
                )

                args = mock_calc.call_args[0]
                self.assertEqual(args[0], "top-left")

    def test_render_group_uses_custom_alignment(self):
        settings = {"display": True, "align": "bottom-right", "offset": (10, 20)}

        with patch('pygame.display.get_window_size', return_value=(800, 600)):
            with patch('v3xctrl_ui.osd.WidgetGroupRenderer.calculate_widget_position') as mock_calc:
                mock_calc.return_value = (100, 200)

                WidgetGroupRenderer.render_group(
                    self.screen,
                    self.widgets,
                    settings,
                    self.widget_settings,
                    self.get_value
                )

                args = mock_calc.call_args[0]
                self.assertEqual(args[0], "bottom-right")

    def test_render_group_applies_rounded_corners(self):
        settings = {"display": True}

        with patch('pygame.display.get_window_size', return_value=(800, 600)):
            with patch('v3xctrl_ui.osd.WidgetGroupRenderer.round_corners') as mock_round:
                mock_surface = pygame.Surface((100, 50), pygame.SRCALPHA)
                mock_round.return_value = mock_surface

                WidgetGroupRenderer.render_group(
                    self.screen,
                    self.widgets,
                    settings,
                    self.widget_settings,
                    self.get_value
                )

                mock_round.assert_called_once()
                self.assertEqual(mock_round.call_args[0][1], 4)

    def test_render_group_with_custom_corner_radius(self):
        settings = {"display": True}

        with patch('pygame.display.get_window_size', return_value=(800, 600)):
            with patch('v3xctrl_ui.osd.WidgetGroupRenderer.round_corners') as mock_round:
                mock_surface = pygame.Surface((100, 50), pygame.SRCALPHA)
                mock_round.return_value = mock_surface

                WidgetGroupRenderer.render_group(
                    self.screen,
                    self.widgets,
                    settings,
                    self.widget_settings,
                    self.get_value,
                    corner_radius=10
                )

                self.assertEqual(mock_round.call_args[0][1], 10)


if __name__ == "__main__":
    unittest.main()
