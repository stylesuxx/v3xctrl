import unittest
from typing import Any

from v3xctrl_control.mixer import Ackermann

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


def make_ackermann(**overrides: Any) -> Ackermann:
    return Ackermann(**{**ACKERMANN_DEFAULTS, **overrides})


class TestAckermann(unittest.TestCase):
    def test_idle_centers_steering(self) -> None:
        self.assertEqual(make_ackermann().idle, (1500, 1500))

    def test_idle_shifts_with_trim(self) -> None:
        self.assertEqual(make_ackermann(steering_trim=40).idle, (1500, 1540))

    def test_idle_clamps_trim_to_steering_range(self) -> None:
        self.assertEqual(make_ackermann(steering_trim=900).idle, (1500, 2000))

    def test_idle_follows_steering_direction_when_inverted(self) -> None:
        self.assertEqual(make_ackermann(steering_invert=True, steering_trim=40).idle, (1500, 1460))

    def test_idle_matches_where_the_servo_sits_while_driving(self) -> None:
        for invert in (False, True):
            with self.subTest(steering_invert=invert):
                mixer = make_ackermann(steering_invert=invert, steering_trim=40)
                self.assertEqual(mixer.idle[1], mixer.calculate_channel_values(0.0, 0.0)[1])

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
