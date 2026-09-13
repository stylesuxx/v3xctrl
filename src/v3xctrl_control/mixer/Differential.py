from argparse import Namespace
from typing import Self

from v3xctrl_helper import apply_expo

from .Mixer import Mixer, apply_balance, esc_pulse_width, mix_differential


class Differential(Mixer):
    """
    Left motor on channel A, right motor on channel B, both driven from one shared profile.
    """

    def __init__(
        self,
        *,
        motor_min: int,
        motor_max: int,
        motor_idle: int,
        motor_failsafe: int,
        motor_scale_forward: int,
        motor_scale_reverse: int,
        motor_expo: int,
        motor_reversible: bool,
        motor_a_min_forward: int,
        motor_a_min_reverse: int,
        motor_b_min_forward: int,
        motor_b_min_reverse: int,
        mixing_scale: int,
        mixing_invert: bool,
        mixing_expo: int,
        mixing_balance: int,
    ) -> None:
        self._motor_min = motor_min
        self._motor_max = motor_max
        self._motor_idle = motor_idle
        self._motor_failsafe = motor_failsafe
        self._motor_expo = motor_expo
        self._motor_reversible = motor_reversible

        self._mixing_expo = mixing_expo
        self._mixing_balance = mixing_balance

        self._forward_min_a = motor_idle + motor_a_min_forward
        self._reverse_min_a = motor_idle - motor_a_min_reverse
        self._forward_min_b = motor_idle + motor_b_min_forward
        self._reverse_min_b = motor_idle - motor_b_min_reverse
        self._forward_multiplier = motor_scale_forward / 100.0
        self._reverse_multiplier = motor_scale_reverse / 100.0
        self._mixing_multiplier = mixing_scale / 100.0

        self._mixing_invert_multiplier = -1 if mixing_invert else 1

    @classmethod
    def from_args(cls, args: Namespace) -> Self:
        return cls(
            motor_min=args.differential_motor_min,
            motor_max=args.differential_motor_max,
            motor_idle=args.differential_motor_idle,
            motor_failsafe=args.differential_motor_failsafe,
            motor_scale_forward=args.differential_motor_scale_forward,
            motor_scale_reverse=args.differential_motor_scale_reverse,
            motor_expo=args.differential_motor_expo,
            motor_reversible=args.differential_motor_reversible,
            motor_a_min_forward=args.differential_motor_a_min_forward,
            motor_a_min_reverse=args.differential_motor_a_min_reverse,
            motor_b_min_forward=args.differential_motor_b_min_forward,
            motor_b_min_reverse=args.differential_motor_b_min_reverse,
            mixing_scale=args.differential_mixing_scale,
            mixing_invert=args.differential_mixing_invert,
            mixing_expo=args.differential_mixing_expo,
            mixing_balance=args.differential_mixing_balance,
        )

    def _motor_pulse_width(self, motor_value: float, forward_min: int, reverse_min: int, balance: int) -> int:
        pulse_width = esc_pulse_width(
            motor_value,
            forward_min,
            self._motor_max,
            self._motor_min,
            reverse_min,
            self._forward_multiplier,
            self._reverse_multiplier,
            self._motor_idle,
            reversible=self._motor_reversible,
        )

        return apply_balance(pulse_width, balance, self._motor_idle, self._motor_min, self._motor_max)

    def calculate_channel_values(self, throttle: float, steering: float) -> tuple[int, int]:
        throttle = apply_expo(throttle, self._motor_expo)
        steering = apply_expo(steering, self._mixing_expo)

        signed_steering = steering * self._mixing_multiplier * self._mixing_invert_multiplier
        left, right = mix_differential(throttle, signed_steering)

        channel_a = self._motor_pulse_width(left, self._forward_min_a, self._reverse_min_a, self._mixing_balance)
        channel_b = self._motor_pulse_width(right, self._forward_min_b, self._reverse_min_b, -self._mixing_balance)

        return channel_a, channel_b

    @property
    def idle(self) -> tuple[int, int]:
        return self._motor_idle, self._motor_idle

    @property
    def failsafe(self) -> tuple[int, int]:
        return self._motor_failsafe, self._motor_failsafe

    def adjust_trim(self, step: int) -> tuple[str, int]:
        self._mixing_balance += step

        return ".control.mixer.differential.mixing.balance", self._mixing_balance
