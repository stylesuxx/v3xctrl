# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
from unittest.mock import patch

from v3xctrl_ui.osd.WidgetGroupRenderer import (
    render_widget_group,
    render_group,
    _render_individual_widgets,
    _filter_visible_widgets,
    _calculate_dimensions,
    _draw_widgets_to_surface,
)
from v3xctrl_ui.osd.WidgetGroup import WidgetGroup
from v3xctrl_ui.osd.widgets import TextWidget


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
        visible = _filter_visible_widgets(
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

        visible = _filter_visible_widgets(
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

        visible = _filter_visible_widgets(
            self.widgets,
            widget_settings
        )

        self.assertEqual(len(visible), 3)

    def test_filter_visible_widgets_returns_empty_when_all_hidden(self):
        self.widget_settings["widget1"]["display"] = False
        self.widget_settings["widget2"]["display"] = False
        self.widget_settings["widget3"]["display"] = False

        visible = _filter_visible_widgets(
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

        width, height = _calculate_dimensions(visible, 0)

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

        width, height = _calculate_dimensions(visible, 10)

        self.assertEqual(width, 100)
        self.assertEqual(height, 60)

    def test_calculate_dimensions_single_widget(self):
        self.widget1.width = 150
        self.widget1.height = 40

        visible = [("widget1", self.widget1)]

        width, height = _calculate_dimensions(visible, 5)

        self.assertEqual(width, 150)
        self.assertEqual(height, 40)

    def test_calculate_dimensions_empty_list(self):
        visible = []

        width, height = _calculate_dimensions(visible, 5)

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

        _draw_widgets_to_surface(
            surface, visible, self.get_value, 5
        )

        self.assertEqual(self.widget1.position, (0, 0))
        self.assertEqual(self.widget2.position, (0, 25))
        self.assertEqual(self.widget3.position, (0, 60))

    def test_draw_widgets_to_surface_calls_draw_with_values(self):
        surface = pygame.Surface((100, 50), pygame.SRCALPHA)
        visible = [("widget1", self.widget1)]

        with patch.object(self.widget1, 'draw') as mock_draw:
            _draw_widgets_to_surface(
                surface, visible, self.get_value, 0
            )
            mock_draw.assert_called_once_with(surface, "Value for widget1")

    def test_render_group_uses_default_alignment(self):
        settings = {"display": True}

        with patch('pygame.display.get_window_size', return_value=(800, 600)):
            with patch('v3xctrl_ui.osd.WidgetGroupRenderer.calculate_widget_position') as mock_calc:
                mock_calc.return_value = (0, 0)

                render_group(
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

                render_group(
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

                render_group(
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

                render_group(
                    self.screen,
                    self.widgets,
                    settings,
                    self.widget_settings,
                    self.get_value,
                    corner_radius=10
                )

                self.assertEqual(mock_round.call_args[0][1], 10)

    def test_render_individual_widgets(self):
        """Test _render_individual_widgets renders widgets at their individual positions."""
        widget_settings = {
            "widget1": {"display": True, "align": "top-left", "offset": (10, 10)},
            "widget2": {"display": True, "align": "top-right", "offset": (20, 20)},
            "widget3": {"display": False, "align": "bottom-left", "offset": (0, 0)}
        }

        with patch('pygame.display.get_window_size', return_value=(800, 600)):
            with patch('v3xctrl_ui.osd.WidgetGroupRenderer.calculate_widget_position') as mock_calc:
                mock_calc.side_effect = [(10, 10), (780, 20)]

                _render_individual_widgets(
                    self.screen,
                    self.widgets,
                    widget_settings,
                    self.get_value
                )

                # Should only position visible widgets (widget1 and widget2)
                self.assertEqual(mock_calc.call_count, 2)
                self.assertEqual(self.widget1.position, (10, 10))
                self.assertEqual(self.widget2.position, (780, 20))

    def test_render_widget_group_composition_mode(self):
        """Test render_widget_group with composition mode."""
        widgets = {
            "widget1": self.widget1,
            "widget2": self.widget2
        }
        widget_settings = {
            "test_group": {"display": True, "align": "center"},
            "widget1": {"display": True},
            "widget2": {"display": True}
        }

        group = WidgetGroup.create(
            name="test_group",
            widgets=widgets,
            get_value=self.get_value,
            use_composition=True,
            corner_radius=6
        )

        with patch('pygame.display.get_window_size', return_value=(800, 600)):
            with patch('v3xctrl_ui.osd.WidgetGroupRenderer.render_group') as mock_render:
                render_widget_group(
                    self.screen,
                    group,
                    widget_settings
                )

                mock_render.assert_called_once()
                call_args = mock_render.call_args[0]
                self.assertEqual(call_args[0], self.screen)
                self.assertEqual(call_args[5], 6)  # corner_radius

    def test_render_widget_group_individual_mode(self):
        """Test render_widget_group with individual rendering mode."""
        widgets = {
            "widget1": self.widget1
        }
        widget_settings = {
            "test_group": {"display": True},
            "widget1": {"display": True, "align": "center", "offset": (0, 0)}
        }

        group = WidgetGroup.create(
            name="test_group",
            widgets=widgets,
            get_value=self.get_value,
            use_composition=False
        )

        with patch('pygame.display.get_window_size', return_value=(800, 600)):
            with patch('v3xctrl_ui.osd.WidgetGroupRenderer._render_individual_widgets') as mock_render:
                render_widget_group(
                    self.screen,
                    group,
                    widget_settings
                )

                mock_render.assert_called_once()


if __name__ == "__main__":
    unittest.main()
