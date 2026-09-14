import unittest

from v3xctrl_control.mixer import esc_pulse_width, map_range

FORWARD_MIN = 1500
THROTTLE_MAX = 2000
THROTTLE_MIN = 1000
REVERSE_MIN = 1500
IDLE = 1500


class TestMapRange(unittest.TestCase):
    def test_maps_midpoint(self) -> None:
        self.assertEqual(map_range(0, -1, 1, 1000, 2000), 1500)

    def test_maps_endpoints(self) -> None:
        self.assertEqual(map_range(-1, -1, 1, 1000, 2000), 1000)
        self.assertEqual(map_range(1, -1, 1, 1000, 2000), 2000)

    def test_clamps_out_of_range_input(self) -> None:
        self.assertEqual(map_range(5, -1, 1, 1000, 2000), 2000)
        self.assertEqual(map_range(-5, -1, 1, 1000, 2000), 1000)

    def test_zero_input_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            map_range(0, 1, 1)


class TestEscPulseWidthReversible(unittest.TestCase):
    def test_forward(self) -> None:
        value = esc_pulse_width(
            0.5, FORWARD_MIN, THROTTLE_MAX, THROTTLE_MIN, REVERSE_MIN, 1.0, 1.0, IDLE, reversible=True
        )
        self.assertEqual(value, 1750)

    def test_reverse(self) -> None:
        value = esc_pulse_width(
            -0.5, FORWARD_MIN, THROTTLE_MAX, THROTTLE_MIN, REVERSE_MIN, 1.0, 1.0, IDLE, reversible=True
        )
        self.assertEqual(value, 1250)

    def test_zero_falls_through_to_idle(self) -> None:
        value = esc_pulse_width(
            0, FORWARD_MIN, THROTTLE_MAX, THROTTLE_MIN, REVERSE_MIN, 1.0, 1.0, IDLE, reversible=True
        )
        self.assertEqual(value, IDLE)

    def test_forward_multiplier_scales_output(self) -> None:
        value = esc_pulse_width(
            1.0, FORWARD_MIN, THROTTLE_MAX, THROTTLE_MIN, REVERSE_MIN, 0.5, 1.0, IDLE, reversible=True
        )
        self.assertEqual(value, 1750)

    def test_reverse_multiplier_scales_output(self) -> None:
        value = esc_pulse_width(
            -1.0, FORWARD_MIN, THROTTLE_MAX, THROTTLE_MIN, REVERSE_MIN, 1.0, 0.5, IDLE, reversible=True
        )
        self.assertEqual(value, 1250)


class TestEscPulseWidthNonReversible(unittest.TestCase):
    def test_forward_matches_reversible_behavior(self) -> None:
        reversible = esc_pulse_width(
            0.5, FORWARD_MIN, THROTTLE_MAX, THROTTLE_MIN, REVERSE_MIN, 1.0, 1.0, IDLE, reversible=True
        )
        non_reversible = esc_pulse_width(
            0.5, FORWARD_MIN, THROTTLE_MAX, THROTTLE_MIN, REVERSE_MIN, 1.0, 1.0, IDLE, reversible=False
        )
        self.assertEqual(reversible, non_reversible)

    def test_zero_returns_idle(self) -> None:
        value = esc_pulse_width(
            0, FORWARD_MIN, THROTTLE_MAX, THROTTLE_MIN, REVERSE_MIN, 1.0, 1.0, IDLE, reversible=False
        )
        self.assertEqual(value, IDLE)

    def test_negative_returns_idle_instead_of_reversing(self) -> None:
        value = esc_pulse_width(
            -0.5, FORWARD_MIN, THROTTLE_MAX, THROTTLE_MIN, REVERSE_MIN, 1.0, 1.0, IDLE, reversible=False
        )
        self.assertEqual(value, IDLE)
