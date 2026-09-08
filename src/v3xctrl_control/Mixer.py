from abc import ABC, abstractmethod
from argparse import Namespace
from enum import StrEnum
from typing import Self

from v3xctrl_helper import apply_expo, clamp


class MixerType(StrEnum):
    ACKERMANN = "ackermann"
    DIFFERENTIAL = "differential"


def map_range(value: float, in_min: float, in_max: float, servo_min: int = 1000, servo_max: int = 2000) -> int:
    """
    Maps a float value from an input range [in_min, in_max] to a servo PWM pulse width.

    Args:
        value: Input value to map.
        in_min: Minimum of input range.
        in_max: Maximum of input range.
        servo_min: Minimum servo pulse width in microseconds.
        servo_max: Maximum servo pulse width in microseconds.

    Returns:
        Mapped servo pulse width as integer in microseconds.
    """
    if in_min == in_max:
        raise ValueError("Input range cannot be zero")

    clamped = clamp(value, in_min, in_max)
    normalized = (clamped - in_min) / (in_max - in_min)

    return int(servo_min + normalized * (servo_max - servo_min))


def mix_differential(throttle: float, steering: float) -> tuple[float, float]:
    """
    Combines throttle and steering into left/right motor values for differential thrust.
    """
    left = clamp(throttle + steering, -1, 1)
    right = clamp(throttle - steering, -1, 1)

    return left, right


def esc_pulse_width(
    value: float,
    forward_min: int,
    throttle_max: int,
    throttle_min: int,
    reverse_min: int,
    forward_multiplier: float,
    reverse_multiplier: float,
    idle: int,
    reversible: bool,
) -> int:
    """
    Maps a normalized [-1, 1] motor value to an ESC pulse width.

    Values at or below zero return idle when the motor is not reversible, since a
    unidirectional ESC has no reverse range to map into.

    Args:
        value: Normalized motor value in [-1, 1].
        forward_min: Minimum pulse width for the forward range (idle + forward boost).
        throttle_max: Maximum pulse width in microseconds.
        throttle_min: Minimum pulse width in microseconds.
        reverse_min: Minimum pulse width for the reverse range (idle - reverse boost).
        forward_multiplier: Scale applied to positive values before mapping.
        reverse_multiplier: Scale applied to negative values before mapping.
        idle: Pulse width returned for zero, and for negative values when not reversible.
        reversible: Whether the motor accepts a reverse pulse range.

    Returns:
        Mapped ESC pulse width as integer in microseconds.
    """
    if value > 0:
        scaled = value * forward_multiplier

        return map_range(scaled, 0, 1, forward_min, throttle_max)

    if value < 0 and reversible:
        scaled = value * reverse_multiplier

        return map_range(scaled, -1, 0, throttle_min, reverse_min)

    return idle


def apply_balance(pulse_width: int, balance: int, idle: int, motor_min: int, motor_max: int) -> int:
    """
    Applies a live balance/trim offset to a motor's pulse width, clamped to [motor_min, motor_max].

    The offset is skipped whenever the motor is at idle (stopped, or a non-reversible
    motor told to reverse), so trimming never causes a motor to move away from rest.
    """
    if pulse_width == idle:
        return pulse_width

    return int(clamp(pulse_width + balance, motor_min, motor_max))


class Mixer(ABC):
    """
    A mixer owns the complete settings of one vehicle layout and turns the wire-level
    throttle/steering pair into the two physical PWM channel values.
    """

    @classmethod
    @abstractmethod
    def from_args(cls, args: Namespace) -> Self:
        """Builds the mixer from the parsed command line arguments."""

    @abstractmethod
    def calculate_channel_values(self, throttle: float, steering: float) -> tuple[int, int]:
        """Maps a normalized throttle/steering pair to (channel A, channel B) pulse widths."""

    @property
    @abstractmethod
    def idle(self) -> tuple[int, int]:
        """Pulse widths the channels rest at on startup and shutdown."""

    @property
    @abstractmethod
    def failsafe(self) -> tuple[int, int]:
        """Pulse widths sent when the link is lost or the failsafe timeout expires."""

    @abstractmethod
    def adjust_trim(self, step: int) -> tuple[str, int]:
        """
        Applies a single trim step.

        Returns:
            The config path to persist the new value under, and the value itself.
        """


class Ackermann(Mixer):
    """
    Throttle on channel A, steering servo on channel B.
    """

    def __init__(
        self,
        *,
        throttle_min: int,
        throttle_max: int,
        throttle_idle: int,
        throttle_failsafe: int,
        throttle_scale_forward: int,
        throttle_scale_reverse: int,
        throttle_min_forward: int,
        throttle_min_reverse: int,
        throttle_expo: int,
        steering_min: int,
        steering_max: int,
        steering_failsafe: int,
        steering_trim: int,
        steering_scale: int,
        steering_invert: bool,
        steering_expo: int,
    ) -> None:
        self._throttle_min = throttle_min
        self._throttle_max = throttle_max
        self._throttle_idle = throttle_idle
        self._throttle_failsafe = throttle_failsafe
        self._throttle_expo = throttle_expo

        self._steering_min = steering_min
        self._steering_max = steering_max
        self._steering_failsafe = steering_failsafe
        self._steering_trim = steering_trim
        self._steering_expo = steering_expo

        self._forward_min = throttle_idle + throttle_min_forward
        self._reverse_min = throttle_idle - throttle_min_reverse
        self._forward_multiplier = throttle_scale_forward / 100.0
        self._reverse_multiplier = throttle_scale_reverse / 100.0
        self._steering_multiplier = steering_scale / 100.0

        self._steering_left = 1 if steering_invert else -1
        self._steering_right = -1 if steering_invert else 1
        self._trim_multiplier = -1 if steering_invert else 1

    @classmethod
    def from_args(cls, args: Namespace) -> Self:
        return cls(
            throttle_min=args.ackermann_throttle_min,
            throttle_max=args.ackermann_throttle_max,
            throttle_idle=args.ackermann_throttle_idle,
            throttle_failsafe=args.ackermann_throttle_failsafe,
            throttle_scale_forward=args.ackermann_throttle_scale_forward,
            throttle_scale_reverse=args.ackermann_throttle_scale_reverse,
            throttle_min_forward=args.ackermann_throttle_min_forward,
            throttle_min_reverse=args.ackermann_throttle_min_reverse,
            throttle_expo=args.ackermann_throttle_expo,
            steering_min=args.ackermann_steering_min,
            steering_max=args.ackermann_steering_max,
            steering_failsafe=args.ackermann_steering_failsafe,
            steering_trim=args.ackermann_steering_trim,
            steering_scale=args.ackermann_steering_scale,
            steering_invert=args.ackermann_steering_invert,
            steering_expo=args.ackermann_steering_expo,
        )

    def calculate_channel_values(self, throttle: float, steering: float) -> tuple[int, int]:
        throttle = apply_expo(throttle, self._throttle_expo)
        steering = apply_expo(steering, self._steering_expo)

        channel_a = esc_pulse_width(
            throttle,
            self._forward_min,
            self._throttle_max,
            self._throttle_min,
            self._reverse_min,
            self._forward_multiplier,
            self._reverse_multiplier,
            self._throttle_idle,
            reversible=True,
        )

        mapped_steering = map_range(
            steering * self._steering_multiplier,
            self._steering_left,
            self._steering_right,
            self._steering_min,
            self._steering_max,
        )
        trimmed_steering = mapped_steering + (self._steering_trim * self._trim_multiplier)
        channel_b = int(clamp(trimmed_steering, self._steering_min, self._steering_max))

        return channel_a, channel_b

    @property
    def idle(self) -> tuple[int, int]:
        # The trim multiplier is deliberately not applied here, to reproduce the behaviour
        # of the code this class replaces. Fixed in the follow-up commit.
        center = (self._steering_max + self._steering_min) / 2 + self._steering_trim

        return self._throttle_idle, int(clamp(center, self._steering_min, self._steering_max))

    @property
    def failsafe(self) -> tuple[int, int]:
        return self._throttle_failsafe, self._steering_failsafe

    def adjust_trim(self, step: int) -> tuple[str, int]:
        self._steering_trim += step

        return ".control.mixer.ackermann.steering.trim", self._steering_trim


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
