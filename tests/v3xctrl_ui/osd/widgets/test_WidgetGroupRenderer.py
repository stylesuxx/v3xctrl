# Required before importing pygame, otherwise screen might flicker during tests
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import patch

import pygame

from v3xctrl_ui.core.SettingsSchema import WidgetAlignment, WidgetConfig, WidgetSettings
from v3xctrl_ui.osd.widgets import TextWidget, Widget
from v3xctrl_ui.osd.widgets.TextWidget import ColoredText
from v3xctrl_ui.osd.widgets.WidgetGroup import WidgetEntry, WidgetGroup
from v3xctrl_ui.osd.widgets.WidgetGroupRenderer import (
    _calculate_dimensions,
    _draw_entries_to_surface,
    _filter_visible_entries,
    _render_individual_widgets,
    render_group,
    render_widget_group,
)


def entry(name: str, widget: Widget) -> WidgetEntry:
    return WidgetEntry(name, widget, lambda: ColoredText(f"Value for {name}"))


class TestWidgetGroupRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.screen = pygame.Surface((800, 600), pygame.SRCALPHA)

        self.widget1 = TextWidget((0, 0), 100)
        self.widget2 = TextWidget((0, 0), 100)
        self.widget3 = TextWidget((0, 0), 100)

        self.entry1 = entry("widget1", self.widget1)
        self.entry2 = entry("widget2", self.widget2)
        self.entry3 = entry("widget3", self.widget3)
        self.entries = (self.entry1, self.entry2, self.entry3)

        self.widget_settings = WidgetSettings(
            configs={
                "widget1": WidgetConfig(display=True),
                "widget2": WidgetConfig(display=True),
                "widget3": WidgetConfig(display=True),
            }
        )

    def test_filter_visible_entries_returns_all_when_all_visible(self):
        visible = _filter_visible_entries(self.entries, self.widget_settings)

        self.assertEqual(len(visible), 3)
        names = [visible_entry.name for visible_entry in visible]
        self.assertIn("widget1", names)
        self.assertIn("widget2", names)
        self.assertIn("widget3", names)

    def test_filter_visible_entries_filters_hidden_widgets(self):
        self.widget_settings = self.widget_settings.with_display("widget2", False)

        visible = _filter_visible_entries(self.entries, self.widget_settings)

        self.assertEqual(len(visible), 2)
        names = [visible_entry.name for visible_entry in visible]
        self.assertIn("widget1", names)
        self.assertNotIn("widget2", names)
        self.assertIn("widget3", names)

    def test_filter_visible_entries_defaults_to_visible_when_no_settings(self):
        widget_settings = WidgetSettings(configs={})

        visible = _filter_visible_entries(self.entries, widget_settings)

        self.assertEqual(len(visible), 3)

    def test_filter_visible_entries_returns_empty_when_all_hidden(self):
        for name in ("widget1", "widget2", "widget3"):
            self.widget_settings = self.widget_settings.with_display(name, False)

        visible = _filter_visible_entries(self.entries, self.widget_settings)

        self.assertEqual(len(visible), 0)

    def test_calculate_dimensions_with_no_padding(self):
        self.widget1.width = 100
        self.widget1.height = 20
        self.widget2.width = 80
        self.widget2.height = 30
        self.widget3.width = 120
        self.widget3.height = 25

        width, height = _calculate_dimensions(self.entries, 0)

        self.assertEqual(width, 120)
        self.assertEqual(height, 75)

    def test_calculate_dimensions_with_padding(self):
        self.widget1.width = 100
        self.widget1.height = 20
        self.widget2.width = 80
        self.widget2.height = 30

        width, height = _calculate_dimensions((self.entry1, self.entry2), 10)

        self.assertEqual(width, 100)
        self.assertEqual(height, 60)

    def test_calculate_dimensions_single_widget(self):
        self.widget1.width = 150
        self.widget1.height = 40

        width, height = _calculate_dimensions((self.entry1,), 5)

        self.assertEqual(width, 150)
        self.assertEqual(height, 40)

    def test_calculate_dimensions_empty_list(self):
        width, height = _calculate_dimensions((), 5)

        self.assertEqual(width, 0)
        self.assertEqual(height, 0)

    def test_draw_entries_to_surface_sets_positions(self):
        self.widget1.height = 20
        self.widget2.height = 30
        self.widget3.height = 25

        surface = pygame.Surface((100, 85), pygame.SRCALPHA)

        _draw_entries_to_surface(surface, self.entries, 5)

        self.assertEqual(self.widget1.position, (0, 0))
        self.assertEqual(self.widget2.position, (0, 25))
        self.assertEqual(self.widget3.position, (0, 60))

    def test_draw_entries_to_surface_draws_each_widget_with_its_own_value(self):
        surface = pygame.Surface((100, 50), pygame.SRCALPHA)

        with patch.object(self.widget1, "draw") as mock_draw:
            _draw_entries_to_surface(surface, (self.entry1,), 0)
            mock_draw.assert_called_once_with(surface, ColoredText("Value for widget1"))

    def test_a_value_is_read_once_per_widget_per_render(self):
        """Each widget pulls its own value, so a group costs one read per widget."""
        reads = []

        def read_value():
            reads.append(1)
            return ColoredText("read")

        counted = WidgetEntry("widget1", self.widget1, read_value)
        surface = pygame.Surface((100, 50), pygame.SRCALPHA)

        _draw_entries_to_surface(surface, (counted,), 0)

        self.assertEqual(len(reads), 1)

    def test_render_group_uses_default_alignment(self):
        settings = WidgetConfig(display=True)

        with (
            patch("pygame.display.get_window_size", return_value=(800, 600)),
            patch("v3xctrl_ui.osd.widgets.WidgetGroupRenderer.calculate_widget_position") as mock_calc,
        ):
            mock_calc.return_value = (0, 0)

            render_group(self.screen, self.entries, settings, self.widget_settings)

            args = mock_calc.call_args[0]
            self.assertEqual(args[0], "top-left")

    def test_render_group_uses_custom_alignment(self):
        settings = WidgetConfig(display=True, align=WidgetAlignment.BOTTOM_RIGHT, offset=(10, 20))

        with (
            patch("pygame.display.get_window_size", return_value=(800, 600)),
            patch("v3xctrl_ui.osd.widgets.WidgetGroupRenderer.calculate_widget_position") as mock_calc,
        ):
            mock_calc.return_value = (100, 200)

            render_group(self.screen, self.entries, settings, self.widget_settings)

            args = mock_calc.call_args[0]
            self.assertEqual(args[0], "bottom-right")

    def test_render_group_applies_rounded_corners(self):
        settings = WidgetConfig(display=True)

        with (
            patch("pygame.display.get_window_size", return_value=(800, 600)),
            patch("v3xctrl_ui.osd.widgets.WidgetGroupRenderer.round_corners") as mock_round,
        ):
            mock_surface = pygame.Surface((100, 50), pygame.SRCALPHA)
            mock_round.return_value = mock_surface

            render_group(self.screen, self.entries, settings, self.widget_settings)

            mock_round.assert_called_once()
            self.assertEqual(mock_round.call_args[0][1], 4)

    def test_render_group_with_custom_corner_radius(self):
        settings = WidgetConfig(display=True)

        with (
            patch("pygame.display.get_window_size", return_value=(800, 600)),
            patch("v3xctrl_ui.osd.widgets.WidgetGroupRenderer.round_corners") as mock_round,
        ):
            mock_surface = pygame.Surface((100, 50), pygame.SRCALPHA)
            mock_round.return_value = mock_surface

            render_group(self.screen, self.entries, settings, self.widget_settings, corner_radius=10)

            self.assertEqual(mock_round.call_args[0][1], 10)

    def test_render_individual_widgets(self):
        """Test _render_individual_widgets renders widgets at their individual positions."""
        widget_settings = WidgetSettings(
            configs={
                "widget1": WidgetConfig(display=True, align=WidgetAlignment.TOP_LEFT, offset=(10, 10)),
                "widget2": WidgetConfig(display=True, align=WidgetAlignment.TOP_RIGHT, offset=(20, 20)),
                "widget3": WidgetConfig(display=False, align=WidgetAlignment.BOTTOM_LEFT, offset=(0, 0)),
            }
        )

        with (
            patch("pygame.display.get_window_size", return_value=(800, 600)),
            patch("v3xctrl_ui.osd.widgets.WidgetGroupRenderer.calculate_widget_position") as mock_calc,
        ):
            mock_calc.side_effect = [(10, 10), (780, 20)]

            _render_individual_widgets(self.screen, self.entries, widget_settings)

            # Should only position visible widgets (widget1 and widget2)
            self.assertEqual(mock_calc.call_count, 2)
            self.assertEqual(self.widget1.position, (10, 10))
            self.assertEqual(self.widget2.position, (780, 20))

    def test_render_widget_group_composition_mode(self):
        """Test render_widget_group with composition mode."""
        widget_settings = WidgetSettings(
            configs={
                "test_group": WidgetConfig(display=True),
                "widget1": WidgetConfig(display=True),
                "widget2": WidgetConfig(display=True),
            }
        )

        group = WidgetGroup(
            name="test_group", entries=(self.entry1, self.entry2), use_composition=True, corner_radius=6
        )

        with (
            patch("pygame.display.get_window_size", return_value=(800, 600)),
            patch("v3xctrl_ui.osd.widgets.WidgetGroupRenderer.render_group") as mock_render,
        ):
            render_widget_group(self.screen, group, widget_settings)

            mock_render.assert_called_once()
            call_args = mock_render.call_args[0]
            self.assertEqual(call_args[0], self.screen)
            self.assertEqual(call_args[4], 6)  # corner_radius

    def test_render_widget_group_individual_mode(self):
        """Test render_widget_group with individual rendering mode."""
        widget_settings = WidgetSettings(
            configs={
                "test_group": WidgetConfig(display=True),
                "widget1": WidgetConfig(display=True, offset=(0, 0)),
            }
        )

        group = WidgetGroup(name="test_group", entries=(self.entry1,), use_composition=False)

        with (
            patch("pygame.display.get_window_size", return_value=(800, 600)),
            patch("v3xctrl_ui.osd.widgets.WidgetGroupRenderer._render_individual_widgets") as mock_render,
        ):
            render_widget_group(self.screen, group, widget_settings)

            mock_render.assert_called_once()


if __name__ == "__main__":
    unittest.main()
