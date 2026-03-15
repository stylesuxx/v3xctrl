import time
import unittest
from collections import deque

from v3xctrl_ui.utils.helpers import (
    _interpolate_color,
    get_fps,
    interpolate_steering_color,
    interpolate_throttle_color,
)


class TestInterpolateColor(unittest.TestCase):
    def test_value_zero_is_blue(self):
        self.assertEqual(_interpolate_color(0.0), (0, 0, 255))

    def test_value_half_is_green(self):
        self.assertEqual(_interpolate_color(0.5), (0, 255, 0))

    def test_value_one_is_red(self):
        self.assertEqual(_interpolate_color(1.0), (255, 0, 0))

    def test_value_quarter(self):
        result = _interpolate_color(0.25)
        self.assertEqual(result, (0, 127, 127))

    def test_value_three_quarters(self):
        result = _interpolate_color(0.75)
        self.assertEqual(result, (127, 127, 0))

    def test_returns_tuple_of_three_ints(self):
        result = _interpolate_color(0.3)
        self.assertEqual(len(result), 3)
        for component in result:
            self.assertIsInstance(component, int)


class TestInterpolateSteeringColor(unittest.TestCase):
    def test_zero_steering_is_blue(self):
        self.assertEqual(interpolate_steering_color(0.0), (0, 0, 255))

    def test_full_right_steering_is_red(self):
        self.assertEqual(interpolate_steering_color(1.0), (255, 0, 0))

    def test_full_left_steering_is_red(self):
        self.assertEqual(interpolate_steering_color(-1.0), (255, 0, 0))

    def test_half_steering_is_green(self):
        self.assertEqual(interpolate_steering_color(0.5), (0, 255, 0))

    def test_negative_half_steering_is_green(self):
        self.assertEqual(interpolate_steering_color(-0.5), (0, 255, 0))

    def test_over_range_is_clamped(self):
        self.assertEqual(interpolate_steering_color(2.0), (255, 0, 0))

    def test_under_negative_range_is_clamped(self):
        self.assertEqual(interpolate_steering_color(-2.0), (255, 0, 0))


class TestInterpolateThrottleColor(unittest.TestCase):
    def test_zero_throttle_is_blue(self):
        self.assertEqual(interpolate_throttle_color(0.0), (0, 0, 255))

    def test_full_throttle_is_red(self):
        self.assertEqual(interpolate_throttle_color(1.0), (255, 0, 0))

    def test_half_throttle_is_green(self):
        self.assertEqual(interpolate_throttle_color(0.5), (0, 255, 0))

    def test_over_range_is_clamped(self):
        self.assertEqual(interpolate_throttle_color(2.0), (255, 0, 0))

    def test_negative_is_clamped_to_zero(self):
        self.assertEqual(interpolate_throttle_color(-0.5), (0, 0, 255))


class TestGetFps(unittest.TestCase):
    def test_empty_history_returns_zero(self):
        history = deque()
        self.assertEqual(get_fps(history), 0)

    def test_recent_frames(self):
        now = time.monotonic()
        history = deque([now - 0.1, now - 0.2, now - 0.3])
        result = get_fps(history)
        self.assertEqual(result, 3)

    def test_old_frames_excluded(self):
        now = time.monotonic()
        history = deque([now - 2.0, now - 3.0])
        result = get_fps(history)
        self.assertEqual(result, 0)

    def test_mixed_old_and_recent(self):
        now = time.monotonic()
        history = deque([now - 2.0, now - 0.1, now - 0.2])
        result = get_fps(history)
        self.assertEqual(result, 2)

    def test_custom_window(self):
        now = time.monotonic()
        history = deque([now - 0.5, now - 1.5, now - 2.5])
        result = get_fps(history, window_seconds=2)
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
