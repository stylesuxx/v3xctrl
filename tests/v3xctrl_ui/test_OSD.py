import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from collections import deque
import time
import pygame

from v3xctrl_ui.colors import RED
from v3xctrl_ui.Settings import Settings
from v3xctrl_ui.OSD import OSD
from v3xctrl_control.Message import Latency, Telemetry


class TestOSD(unittest.TestCase):
    def setUp(self):
        pygame.init()
        # Create a temp settings file
        self.tempfile = tempfile.NamedTemporaryFile(delete=False, suffix=".toml")
        self.path = self.tempfile.name
        self.tempfile.close()

        self.settings = Settings(self.path)
        self.osd = OSD(self.settings)
        self.screen = pygame.Surface((self.osd.width, self.osd.height))

    def tearDown(self):
        Path(self.path).unlink(missing_ok=True)

    def test_reset_defaults(self):
        self.osd.reset()
        self.assertEqual(self.osd.debug_data, "waiting")
        self.assertEqual(self.osd.signal_quality, {"rsrq": -1, "rsrp": -1})
        self.assertEqual(self.osd.battery_voltage, "0.00V")
        self.assertEqual(self.osd.battery_percent, "100%")
        self.assertEqual(self.osd.throttle, 0.0)
        self.assertEqual(self.osd.steering, 0.0)

    def test_set_control(self):
        self.osd.set_control(throttle=1.0, steering=-0.5)
        self.assertEqual(self.osd.throttle, 1.0)
        self.assertEqual(self.osd.steering, -0.5)

    def test_update_data_queue(self):
        self.osd.widgets_debug["debug_data"].set_value = MagicMock()
        self.osd.update_data_queue(10)
        self.osd.widgets_debug["debug_data"].set_value.assert_called_with(10)

    def test_update_debug_status(self):
        self.osd.update_debug_status("error")
        self.assertEqual(self.osd.debug_data, "error")

    def test_latency_update_sets_latency(self):
        latency = Latency()
        latency.timestamp = time.time() - 0.05  # ~50ms ago
        self.osd.widgets_debug["debug_latency"].set_value = MagicMock()
        self.osd._latency_update(latency)
        self.osd.widgets_debug["debug_latency"].set_value.assert_called()

    def test_telemetry_update_sets_values(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -9, "rsrp": -95},
            "cell": {"band": 3},
            "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False}
        })
        self.osd._telemetry_update(telemetry)
        self.assertEqual(self.osd.signal_quality["rsrq"], -9)
        self.assertEqual(self.osd.signal_band, "Band 3")
        self.assertEqual(self.osd.battery_percent, "75%")

    def test_render_executes(self):
        self.osd.render(
            self.screen,
            loop_history=deque([time.time() - 0.1 for _ in range(5)]),
            video_history=deque([time.time() - 0.1 for _ in range(5)])
        )

    def test_render_draws_widgets(self):
        self.osd.widget_settings["steering"] = {"display": True}
        self.osd.widget_settings["throttle"] = {"display": True}
        self.osd.widgets["steering"].draw = MagicMock()
        self.osd.widgets["throttle"].draw = MagicMock()

        self.osd.render(
            self.screen,
            loop_history=deque([time.time()]),
            video_history=deque([time.time()])
        )

        self.osd.widgets["steering"].draw.assert_called()
        self.osd.widgets["throttle"].draw.assert_called()

    def test_render_draws_debug(self):
        self.osd.widget_settings["debug"] = {"display": True}
        for key in self.osd.widgets_debug:
            self.osd.widget_settings[key] = {"display": True}
            self.osd.widgets_debug[key].draw = MagicMock()

        self.osd.render(
            self.screen,
            loop_history=deque([time.time()]),
            video_history=deque([time.time()])
        )

        for widget in self.osd.widgets_debug.values():
            widget.draw.assert_called()

    def test_latency_color_ranges(self):
        for delta, expected in [(0.05, "green"), (0.1, "yellow"), (0.2, "red")]:
            msg = Latency()
            msg.timestamp = time.time() - delta
            self.osd._latency_update(msg)
            self.assertEqual(self.osd.debug_latency, expected)

    def test_telemetry_sets_warning_color(self):
        telemetry = Telemetry({
            "sig": {"rsrq": -9, "rsrp": -95},
            "cell": {"band": 3},
            "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": True}
        })
        for widget in self.osd.widgets_battery.values():
            widget.set_text_color = MagicMock()

        self.osd._telemetry_update(telemetry)

        for widget in self.osd.widgets_battery.values():
            widget.set_text_color.assert_called_with(RED)


if __name__ == "__main__":
    pygame.init()
    unittest.main()
