import unittest
from typing import Any

from v3xctrl_control.mixer import Differential

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


def make_differential(**overrides: Any) -> Differential:
    return Differential(**{**DIFFERENTIAL_DEFAULTS, **overrides})


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
