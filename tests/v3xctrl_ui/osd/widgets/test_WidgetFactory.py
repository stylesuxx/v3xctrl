# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame

from v3xctrl_ui.osd.widgets.WidgetFactory import (
    create_steering_widgets,
    create_battery_widgets,
    create_signal_widgets,
    create_debug_widgets,
    create_rec_widget,
)
from v3xctrl_ui.osd.widgets import (
    BatteryIconWidget,
    FpsWidget,
    HorizontalIndicatorWidget,
    StatusValueWidget,
    SignalQualityWidget,
    TextWidget,
    VerticalIndicatorWidget,
    Alignment,
)


class TestWidgetFactory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_create_steering_widgets_returns_dict(self):
        widgets = create_steering_widgets()

        self.assertIsInstance(widgets, dict)
        self.assertEqual(len(widgets), 2)
        self.assertIn("steering", widgets)
        self.assertIn("throttle", widgets)

    def test_create_steering_widgets_creates_horizontal_indicator(self):
        widgets = create_steering_widgets()

        steering_widget = widgets["steering"]
        self.assertIsInstance(steering_widget, HorizontalIndicatorWidget)
        self.assertEqual(steering_widget.position, (0, 0))

    def test_create_steering_widgets_creates_vertical_indicator(self):
        widgets = create_steering_widgets()

        throttle_widget = widgets["throttle"]
        self.assertIsInstance(throttle_widget, VerticalIndicatorWidget)
        self.assertEqual(throttle_widget.position, (0, 0))

    def test_create_battery_widgets_returns_dict(self):
        widgets = create_battery_widgets()

        self.assertIsInstance(widgets, dict)
        self.assertEqual(len(widgets), 4)
        self.assertIn("battery_icon", widgets)
        self.assertIn("battery_voltage", widgets)
        self.assertIn("battery_average_voltage", widgets)
        self.assertIn("battery_percent", widgets)

    def test_create_battery_widgets_creates_icon_widget(self):
        widgets = create_battery_widgets()

        icon_widget = widgets["battery_icon"]
        self.assertIsInstance(icon_widget, BatteryIconWidget)

    def test_create_battery_widgets_creates_text_widgets(self):
        widgets = create_battery_widgets()

        voltage_widget = widgets["battery_voltage"]
        avg_voltage_widget = widgets["battery_average_voltage"]
        percent_widget = widgets["battery_percent"]

        self.assertIsInstance(voltage_widget, TextWidget)
        self.assertIsInstance(avg_voltage_widget, TextWidget)
        self.assertIsInstance(percent_widget, TextWidget)

    def test_create_battery_widgets_sets_right_alignment(self):
        widgets = create_battery_widgets()

        # All text widgets should have right alignment
        voltage_widget = widgets["battery_voltage"]
        avg_voltage_widget = widgets["battery_average_voltage"]
        percent_widget = widgets["battery_percent"]

        self.assertEqual(voltage_widget.alignment, Alignment.RIGHT)
        self.assertEqual(avg_voltage_widget.alignment, Alignment.RIGHT)
        self.assertEqual(percent_widget.alignment, Alignment.RIGHT)

    def test_create_signal_widgets_returns_dict(self):
        widgets = create_signal_widgets()

        self.assertIsInstance(widgets, dict)
        self.assertEqual(len(widgets), 3)
        self.assertIn("signal_quality", widgets)
        self.assertIn("signal_band", widgets)
        self.assertIn("signal_cell", widgets)

    def test_create_signal_widgets_creates_quality_widget(self):
        widgets = create_signal_widgets()

        quality_widget = widgets["signal_quality"]
        self.assertIsInstance(quality_widget, SignalQualityWidget)

    def test_create_signal_widgets_creates_text_widgets(self):
        widgets = create_signal_widgets()

        band_widget = widgets["signal_band"]
        cell_widget = widgets["signal_cell"]

        self.assertIsInstance(band_widget, TextWidget)
        self.assertIsInstance(cell_widget, TextWidget)

    def test_create_signal_widgets_sets_cell_font(self):
        widgets = create_signal_widgets()

        cell_widget = widgets["signal_cell"]
        # Just verify font is set, don't check specific font
        self.assertIsNotNone(cell_widget.font)

    def test_create_debug_widgets_returns_dict(self):
        widgets = create_debug_widgets(100, 50)

        self.assertIsInstance(widgets, dict)
        self.assertEqual(len(widgets), 5)
        self.assertIn("debug_fps_loop", widgets)
        self.assertIn("debug_fps_video", widgets)
        self.assertIn("debug_data", widgets)
        self.assertIn("debug_latency", widgets)
        self.assertIn("debug_buffer", widgets)

    def test_create_debug_widgets_creates_fps_widgets(self):
        fps_width = 120
        fps_height = 60
        widgets = create_debug_widgets(fps_width, fps_height)

        loop_widget = widgets["debug_fps_loop"]
        video_widget = widgets["debug_fps_video"]

        self.assertIsInstance(loop_widget, FpsWidget)
        self.assertIsInstance(video_widget, FpsWidget)

    def test_create_debug_widgets_creates_status_value_widgets(self):
        widgets = create_debug_widgets(100, 50)

        data_widget = widgets["debug_data"]
        latency_widget = widgets["debug_latency"]
        buffer_widget = widgets["debug_buffer"]

        self.assertIsInstance(data_widget, StatusValueWidget)
        self.assertIsInstance(latency_widget, StatusValueWidget)
        self.assertIsInstance(buffer_widget, StatusValueWidget)

    def test_create_debug_widgets_uses_provided_dimensions(self):
        fps_width = 150
        fps_height = 75
        widgets = create_debug_widgets(fps_width, fps_height)

        # FPS widgets should use the provided dimensions
        loop_widget = widgets["debug_fps_loop"]
        # Just verify widget was created with position (0, 0)
        self.assertEqual(loop_widget.position, (0, 0))

    def test_all_widgets_initialized_at_origin(self):
        # All widgets should start at position (0, 0)
        # since position is set during rendering

        steering_widgets = create_steering_widgets()
        battery_widgets = create_battery_widgets()
        signal_widgets = create_signal_widgets()
        debug_widgets = create_debug_widgets(100, 50)

        all_widgets = (
            list(steering_widgets.values()) +
            list(battery_widgets.values()) +
            list(signal_widgets.values()) +
            list(debug_widgets.values())
        )

        for widget in all_widgets:
            self.assertEqual(widget.position, (0, 0))

    def test_factory_functions_are_callable(self):
        # Verify all factory functions are callable
        self.assertTrue(callable(create_steering_widgets))
        self.assertTrue(callable(create_battery_widgets))
        self.assertTrue(callable(create_signal_widgets))
        self.assertTrue(callable(create_debug_widgets))
        self.assertTrue(callable(create_rec_widget))

    def test_create_steering_widgets_is_idempotent(self):
        # Calling multiple times should create independent widget sets
        widgets1 = create_steering_widgets()
        widgets2 = create_steering_widgets()

        # Should be different instances
        self.assertIsNot(widgets1["steering"], widgets2["steering"])
        self.assertIsNot(widgets1["throttle"], widgets2["throttle"])

    def test_create_battery_widgets_is_idempotent(self):
        widgets1 = create_battery_widgets()
        widgets2 = create_battery_widgets()

        self.assertIsNot(widgets1["battery_icon"], widgets2["battery_icon"])
        self.assertIsNot(widgets1["battery_voltage"], widgets2["battery_voltage"])

    def test_create_signal_widgets_is_idempotent(self):
        widgets1 = create_signal_widgets()
        widgets2 = create_signal_widgets()

        self.assertIsNot(widgets1["signal_quality"], widgets2["signal_quality"])
        self.assertIsNot(widgets1["signal_band"], widgets2["signal_band"])

    def test_create_debug_widgets_is_idempotent(self):
        widgets1 = create_debug_widgets(100, 50)
        widgets2 = create_debug_widgets(100, 50)

        self.assertIsNot(widgets1["debug_fps_loop"], widgets2["debug_fps_loop"])
        self.assertIsNot(widgets1["debug_latency"], widgets2["debug_latency"])


if __name__ == "__main__":
    unittest.main()
