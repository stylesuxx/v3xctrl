import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import inspect
import tempfile
import time
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock, patch

import pygame

from v3xctrl_ui.core.dataclasses import GpsFixType
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.core.StatusLevel import StatusLevel
from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.core.TelemetrySink import LatencyReading
from v3xctrl_ui.osd.OSD import OSD
from v3xctrl_ui.osd.widgets.TextWidget import ColoredText
from v3xctrl_ui.utils.colors import GREEN, ORANGE, RED, WHITE


class TestOSD(unittest.TestCase):
    def setUp(self):
        pygame.init()
        # Create a temp settings file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".toml") as tmp:
            self.path = tmp.name

        self.settings = Settings(self.path)
        self.telemetry_context = TelemetryContext()
        self.osd = OSD(self.settings, self.telemetry_context)
        self.screen = pygame.Surface((self.osd.width, self.osd.height))

    def tearDown(self):
        Path(self.path).unlink(missing_ok=True)

    def test_reset_defaults(self):
        self.osd.reset()
        self.assertEqual(self.osd.debug_data, StatusLevel.NEUTRAL)
        self.assertEqual(self.osd.debug_latency, StatusLevel.NEUTRAL)
        self.assertEqual(self.osd.debug_buffer, StatusLevel.NEUTRAL)
        self.assertEqual(self.osd.throttle, 0.0)
        self.assertEqual(self.osd.steering, 0.0)

    def test_rec_group_supplies_the_text_the_widget_draws(self):
        """The REC widget renders whatever it is handed, like any other TextWidget."""
        entry = self._find_entry("rec")

        self.assertEqual(entry.get_value(), ColoredText("REC", WHITE))

    def _find_group(self, name):
        for group in self.osd.widget_groups:
            if group.name == name:
                return group

        raise AssertionError(f"no widget group named {name}")

    def _find_entry(self, name):
        for group in self.osd.widget_groups:
            for entry in group.entries:
                if entry.name == name:
                    return entry

        raise AssertionError(f"no widget entry named {name}")

    def test_every_widget_takes_a_required_value(self):
        """The group renderer hands each widget a value, so none may pad its signature."""
        for group in self.osd.widget_groups:
            for entry in group.entries:
                parameters = list(inspect.signature(entry.widget.draw).parameters.values())

                self.assertEqual(len(parameters), 2, entry.name)
                self.assertEqual(parameters[0].name, "screen", entry.name)
                self.assertIs(parameters[1].default, inspect.Parameter.empty, entry.name)

    def test_every_entry_resolves_a_value(self):
        """No widget is wired to a source that no longer produces anything."""
        self.osd.render(self.screen, deque([time.monotonic()]), deque([time.monotonic()]))

        for group in self.osd.widget_groups:
            for entry in group.entries:
                entry.get_value()

    def test_a_group_reads_its_telemetry_once_per_frame(self):
        """Each getter takes a lock and builds a dataclass, so widgets share one reading."""
        with (
            patch.object(self.telemetry_context, "get_battery", wraps=self.telemetry_context.get_battery) as battery,
            patch.object(self.telemetry_context, "get_signal", wraps=self.telemetry_context.get_signal) as signal,
            patch.object(self.telemetry_context, "get_gps", wraps=self.telemetry_context.get_gps) as gps,
        ):
            self.osd.render(self.screen, deque([time.monotonic()]), deque([time.monotonic()]))

        self.assertEqual(battery.call_count, 1)
        self.assertEqual(signal.call_count, 1)
        self.assertEqual(gps.call_count, 1)

    def test_set_control(self):
        self.osd.set_control(throttle=1.0, steering=-0.5)
        self.assertEqual(self.osd.throttle, 1.0)
        self.assertEqual(self.osd.steering, -0.5)

    def test_update_control_queue(self):
        self.osd.debug_widgets.data.set_value = MagicMock()
        self.osd.update_control_queue(10)
        self.osd.debug_widgets.data.set_value.assert_called_with(10)

    def test_update_debug_status(self):
        self.osd.update_debug_status(StatusLevel.BAD)
        self.assertEqual(self.osd.debug_data, StatusLevel.BAD)

    def test_update_latency_shows_the_measurement(self):
        self.osd.debug_widgets.latency.set_value = MagicMock()

        self.osd.update_latency(LatencyReading(milliseconds=25, level=StatusLevel.GOOD))

        self.assertEqual(self.osd.debug_latency, StatusLevel.GOOD)
        self.osd.debug_widgets.latency.set_value.assert_called_with(25)

    def test_update_latency_shows_no_measurement_when_it_is_not_measurable(self):
        self.osd.debug_widgets.latency.set_value = MagicMock()

        self.osd.update_latency(LatencyReading(is_measurable=False))

        self.assertEqual(self.osd.debug_latency, StatusLevel.NEUTRAL)
        self.osd.debug_widgets.latency.set_value.assert_called_with("N/A")

    def test_battery_text_turns_red_on_a_warning(self):
        entry = self._find_entry("battery_voltage")
        self.telemetry_context.update_battery(
            icon=0, voltage="3.20V", average_voltage="3.20V", percent="5%", current="0mA", warning=True
        )

        self.osd.render(self.screen, deque([time.monotonic()]), deque([time.monotonic()]))

        self.assertEqual(entry.get_value(), ColoredText("3.20V", RED))

    def test_battery_text_is_white_without_a_warning(self):
        entry = self._find_entry("battery_percent")
        self.telemetry_context.update_battery(
            icon=0, voltage="4.00V", average_voltage="4.00V", percent="80%", current="0mA", warning=False
        )

        self.osd.render(self.screen, deque([time.monotonic()]), deque([time.monotonic()]))

        self.assertEqual(entry.get_value(), ColoredText("80%", WHITE))

    def test_gps_fix_carries_a_color_for_the_fix_type(self):
        entry = self._find_entry("gps_fix")
        cases = [
            (GpsFixType.NO_HARDWARE, "NO GPS", WHITE),
            (GpsFixType.NO_FIX, "NO FIX", RED),
            (GpsFixType.DEAD_RECKONING, "DEAD REC", ORANGE),
            (GpsFixType.FIX_3D, "3D FIX", GREEN),
        ]

        for fix_type, label, color in cases:
            self.telemetry_context.update_gps(fix_type=fix_type, speed=0.0, satellites="0 SAT")
            self.osd.render(self.screen, deque([time.monotonic()]), deque([time.monotonic()]))

            self.assertEqual(entry.get_value(), ColoredText(label, color), label)

    @patch("v3xctrl_ui.osd.OSD.pygame.display.get_window_size", return_value=(800, 600))
    def test_render_executes(self, mock_get_size):
        self.osd.render(
            self.screen,
            loop_history=deque([time.time() - 0.1 for _ in range(5)]),
            video_history=deque([time.time() - 0.1 for _ in range(5)]),
        )

    @patch("v3xctrl_ui.osd.OSD.pygame.display.get_window_size", return_value=(800, 600))
    def test_render_draws_widgets(self, mock_get_size):
        self.osd.widget_settings = self.osd.widget_settings.with_display("steering", True).with_display(
            "throttle", True
        )
        self.osd.steering_widgets.steering.draw = MagicMock()
        self.osd.steering_widgets.throttle.draw = MagicMock()

        self.osd.render(self.screen, loop_history=deque([time.time()]), video_history=deque([time.time()]))

        self.osd.steering_widgets.steering.draw.assert_called()
        self.osd.steering_widgets.throttle.draw.assert_called()

    @patch("v3xctrl_ui.osd.OSD.pygame.display.get_window_size", return_value=(800, 600))
    def test_render_draws_debug(self, mock_get_size):
        debug_group = self._find_group("debug")
        self.osd.widget_settings = self.osd.widget_settings.with_display("debug", True)
        for entry in debug_group.entries:
            self.osd.widget_settings = self.osd.widget_settings.with_display(entry.name, True)
            entry.widget.draw = MagicMock()

        self.osd.render(self.screen, loop_history=deque([time.time()]), video_history=deque([time.time()]))

        for entry in debug_group.entries:
            entry.widget.draw.assert_called()


if __name__ == "__main__":
    pygame.init()
    unittest.main()
