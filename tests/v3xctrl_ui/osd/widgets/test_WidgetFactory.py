# Required before importing pygame, otherwise screen might flicker during tests
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import dataclasses
import unittest

import pygame

from v3xctrl_ui.osd.widgets import Alignment
from v3xctrl_ui.osd.widgets.WidgetFactory import (
    create_battery_widgets,
    create_clock_widget,
    create_debug_widgets,
    create_gps_widgets,
    create_rec_widget,
    create_signal_widgets,
    create_steering_widgets,
)


class TestWidgetFactory(unittest.TestCase):
    """The field types are the contract mypy checks; these cover what it cannot."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_battery_text_widgets_are_right_aligned(self):
        widgets = create_battery_widgets()

        self.assertEqual(widgets.voltage.alignment, Alignment.RIGHT)
        self.assertEqual(widgets.average_voltage.alignment, Alignment.RIGHT)
        self.assertEqual(widgets.percent.alignment, Alignment.RIGHT)
        self.assertEqual(widgets.current.alignment, Alignment.RIGHT)

    def test_gps_text_widgets_are_right_aligned(self):
        widgets = create_gps_widgets()

        self.assertEqual(widgets.fix.alignment, Alignment.RIGHT)
        self.assertEqual(widgets.satellites.alignment, Alignment.RIGHT)

    def test_signal_cell_uses_a_narrower_font_than_the_band(self):
        widgets = create_signal_widgets()

        self.assertIsNot(widgets.cell.font, widgets.band.font)

    def test_debug_fps_widgets_take_the_configured_size(self):
        widgets = create_debug_widgets(150, 75)

        self.assertEqual(widgets.fps_loop.size, (150, 75))
        self.assertEqual(widgets.fps_video.size, (150, 75))

    def test_every_widget_starts_at_the_origin(self):
        """The group renderer positions widgets, so the factory must not."""
        for widget in self._all_widgets():
            self.assertEqual(widget.position, (0, 0), type(widget).__name__)

    def test_each_call_builds_its_own_widgets(self):
        """Two OSDs sharing a widget would share its position and colour."""
        first = create_battery_widgets()
        second = create_battery_widgets()

        self.assertIsNot(first.icon, second.icon)
        self.assertIsNot(first.voltage, second.voltage)
        self.assertIsNot(create_steering_widgets().steering, create_steering_widgets().steering)
        self.assertIsNot(create_signal_widgets().quality, create_signal_widgets().quality)
        self.assertIsNot(create_debug_widgets(100, 50).latency, create_debug_widgets(100, 50).latency)
        self.assertIsNot(create_gps_widgets().icon, create_gps_widgets().icon)
        self.assertIsNot(create_rec_widget(), create_rec_widget())
        self.assertIsNot(create_clock_widget(), create_clock_widget())

    def _all_widgets(self):
        bundles = [
            create_steering_widgets(),
            create_battery_widgets(),
            create_signal_widgets(),
            create_debug_widgets(100, 50),
            create_gps_widgets(),
        ]

        widgets = [create_rec_widget(), create_clock_widget()]
        for bundle in bundles:
            widgets.extend(getattr(bundle, field.name) for field in dataclasses.fields(bundle))

        return widgets


if __name__ == "__main__":
    unittest.main()
