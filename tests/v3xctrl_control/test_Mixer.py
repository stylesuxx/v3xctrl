import unittest
from typing import Any

from v3xctrl_control.Mixer import (
    Ackermann,
    Differential,
    apply_balance,
    esc_pulse_width,
    map_range,
    mix_differential,
)

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


ACKERMANN_DEFAULTS: dict[str, Any] = {
    "throttle_min": 1000,
    "throttle_max": 2000,
    "throttle_idle": 1500,
    "throttle_failsafe": 1400,
    "throttle_scale_forward": 100,
    "throttle_scale_reverse": 100,
    "throttle_min_forward": 0,
    "throttle_min_reverse": 0,
    "throttle_expo": 0,
    "steering_min": 1000,
    "steering_max": 2000,
    "steering_failsafe": 1600,
    "steering_trim": 0,
    "steering_scale": 100,
    "steering_invert": False,
    "steering_expo": 0,
}

DIFFERENTIAL_DEFAULTS: dict[str, Any] = {
    "motor_min": 1000,
    "motor_max": 2000,
    "motor_idle": 1500,
    "motor_failsafe": 1450,
    "motor_scale_forward": 100,
    "motor_scale_reverse": 100,
    "motor_expo": 0,
    "motor_reversible": True,
    "motor_a_min_forward": 0,
    "motor_a_min_reverse": 0,
    "motor_b_min_forward": 0,
    "motor_b_min_reverse": 0,
    "mixing_scale": 100,
    "mixing_invert": False,
    "mixing_expo": 0,
    "mixing_balance": 0,
}


def make_ackermann(**overrides: Any) -> Ackermann:
    return Ackermann(**{**ACKERMANN_DEFAULTS, **overrides})


def make_differential(**overrides: Any) -> Differential:
    return Differential(**{**DIFFERENTIAL_DEFAULTS, **overrides})


class TestAckermann(unittest.TestCase):
    def test_idle_centers_steering(self) -> None:
        self.assertEqual(make_ackermann().idle, (1500, 1500))

    def test_idle_shifts_with_trim(self) -> None:
        self.assertEqual(make_ackermann(steering_trim=40).idle, (1500, 1540))

    def test_idle_clamps_trim_to_steering_range(self) -> None:
        self.assertEqual(make_ackermann(steering_trim=900).idle, (1500, 2000))

    def test_failsafe_is_per_channel(self) -> None:
        self.assertEqual(make_ackermann().failsafe, (1400, 1600))

    def test_neutral_input(self) -> None:
        self.assertEqual(make_ackermann().calculate_channel_values(0.0, 0.0), (1500, 1500))

    def test_full_forward_and_right(self) -> None:
        self.assertEqual(make_ackermann().calculate_channel_values(1.0, 1.0), (2000, 2000))

    def test_full_reverse_and_left(self) -> None:
        self.assertEqual(make_ackermann().calculate_channel_values(-1.0, -1.0), (1000, 1000))

    def test_steering_invert_swaps_direction(self) -> None:
        mixer = make_ackermann(steering_invert=True)
        self.assertEqual(mixer.calculate_channel_values(0.0, 1.0)[1], 1000)
        self.assertEqual(mixer.calculate_channel_values(0.0, -1.0)[1], 2000)

    def test_steering_scale_limits_travel(self) -> None:
        mixer = make_ackermann(steering_scale=50)
        self.assertEqual(mixer.calculate_channel_values(0.0, 1.0)[1], 1750)

    def test_throttle_dead_zone_lifts_forward_start(self) -> None:
        barely_moving = make_ackermann().calculate_channel_values(0.01, 0.0)[0]
        self.assertEqual(barely_moving, 1505)

        mixer = make_ackermann(throttle_min_forward=60)
        self.assertEqual(mixer.calculate_channel_values(0.01, 0.0)[0], 1564)

    def test_expo_softens_response_around_center(self) -> None:
        linear = make_ackermann().calculate_channel_values(0.5, 0.0)[0]
        curved = make_ackermann(throttle_expo=50).calculate_channel_values(0.5, 0.0)[0]
        self.assertLess(curved, linear)

    def test_trim_offsets_steering_output(self) -> None:
        mixer = make_ackermann(steering_trim=40)
        self.assertEqual(mixer.calculate_channel_values(0.0, 0.0)[1], 1540)

    def test_adjust_trim_returns_config_path_and_value(self) -> None:
        setting, value = make_ackermann(steering_trim=10).adjust_trim(5)
        self.assertEqual(setting, ".control.mixer.ackermann.steering.trim")
        self.assertEqual(value, 15)

    def test_adjust_trim_moves_idle(self) -> None:
        mixer = make_ackermann()
        mixer.adjust_trim(25)
        self.assertEqual(mixer.idle, (1500, 1525))


class TestDifferential(unittest.TestCase):
    def test_idle_is_the_same_on_both_motors(self) -> None:
        self.assertEqual(make_differential().idle, (1500, 1500))

    def test_failsafe_stops_both_motors(self) -> None:
        self.assertEqual(make_differential().failsafe, (1450, 1450))

    def test_neutral_input(self) -> None:
        self.assertEqual(make_differential().calculate_channel_values(0.0, 0.0), (1500, 1500))

    def test_straight_forward_drives_both_motors_equally(self) -> None:
        self.assertEqual(make_differential().calculate_channel_values(1.0, 0.0), (2000, 2000))

    def test_turn_in_place_opposes_the_motors(self) -> None:
        self.assertEqual(make_differential().calculate_channel_values(0.0, 1.0), (2000, 1000))

    def test_mixing_invert_swaps_turn_direction(self) -> None:
        mixer = make_differential(mixing_invert=True)
        self.assertEqual(mixer.calculate_channel_values(0.0, 1.0), (1000, 2000))

    def test_non_reversible_motor_idles_instead_of_reversing(self) -> None:
        mixer = make_differential(motor_reversible=False)
        self.assertEqual(mixer.calculate_channel_values(0.0, 1.0), (2000, 1500))

    def test_balance_is_applied_with_opposite_sign_per_channel(self) -> None:
        channel_a, channel_b = make_differential(mixing_balance=30).calculate_channel_values(0.5, 0.0)
        self.assertEqual(channel_a - channel_b, 60)

    def test_balance_is_skipped_at_idle(self) -> None:
        mixer = make_differential(mixing_balance=30)
        self.assertEqual(mixer.calculate_channel_values(0.0, 0.0), (1500, 1500))

    def test_per_motor_dead_zones_are_independent(self) -> None:
        mixer = make_differential(motor_a_min_forward=50, motor_b_min_forward=80)
        self.assertEqual(mixer.calculate_channel_values(0.01, 0.0), (1554, 1584))

    def test_mixing_scale_limits_turn_authority(self) -> None:
        mixer = make_differential(mixing_scale=50)
        self.assertEqual(mixer.calculate_channel_values(0.0, 1.0), (1750, 1250))

    def test_adjust_trim_returns_config_path_and_value(self) -> None:
        setting, value = make_differential(mixing_balance=10).adjust_trim(-5)
        self.assertEqual(setting, ".control.mixer.differential.mixing.balance")
        self.assertEqual(value, 5)

    def test_adjust_trim_leaves_idle_untouched(self) -> None:
        mixer = make_differential()
        mixer.adjust_trim(25)
        self.assertEqual(mixer.idle, (1500, 1500))
