import unittest

from src.v3xctrl_control.Mixer import apply_balance, esc_pulse_width, map_range, mix_differential

FORWARD_MIN = 1500
THROTTLE_MAX = 2000
THROTTLE_MIN = 1000
REVERSE_MIN = 1500
IDLE = 1500
MOTOR_MIN = 1000
MOTOR_MAX = 2000


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


class TestMixDifferential(unittest.TestCase):
    def test_straight(self) -> None:
        left, right = mix_differential(0.6, 0.0)
        self.assertEqual((left, right), (0.6, 0.6))

    def test_full_right_turn_in_place(self) -> None:
        left, right = mix_differential(0.0, 1.0)
        self.assertEqual((left, right), (1.0, -1.0))

    def test_full_left_turn_in_place(self) -> None:
        left, right = mix_differential(0.0, -1.0)
        self.assertEqual((left, right), (-1.0, 1.0))

    def test_clamps_when_combined_exceeds_range(self) -> None:
        left, right = mix_differential(0.8, 0.5)
        self.assertEqual(left, 1.0)
        self.assertAlmostEqual(right, 0.3)

    def test_reverse_throttle_with_steering(self) -> None:
        left, right = mix_differential(-0.6, 0.2)
        self.assertAlmostEqual(left, -0.4)
        self.assertAlmostEqual(right, -0.8)


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


class TestApplyBalance(unittest.TestCase):
    def test_skips_offset_when_at_idle(self) -> None:
        value = apply_balance(IDLE, 50, IDLE, MOTOR_MIN, MOTOR_MAX)
        self.assertEqual(value, IDLE)

    def test_skips_negative_offset_when_at_idle(self) -> None:
        value = apply_balance(IDLE, -50, IDLE, MOTOR_MIN, MOTOR_MAX)
        self.assertEqual(value, IDLE)

    def test_applies_positive_offset_when_moving(self) -> None:
        value = apply_balance(1750, 50, IDLE, MOTOR_MIN, MOTOR_MAX)
        self.assertEqual(value, 1800)

    def test_applies_negative_offset_when_moving(self) -> None:
        value = apply_balance(1750, -50, IDLE, MOTOR_MIN, MOTOR_MAX)
        self.assertEqual(value, 1700)

    def test_clamps_to_motor_max(self) -> None:
        value = apply_balance(1980, 50, IDLE, MOTOR_MIN, MOTOR_MAX)
        self.assertEqual(value, MOTOR_MAX)

    def test_clamps_to_motor_min(self) -> None:
        value = apply_balance(1020, -50, IDLE, MOTOR_MIN, MOTOR_MAX)
        self.assertEqual(value, MOTOR_MIN)
