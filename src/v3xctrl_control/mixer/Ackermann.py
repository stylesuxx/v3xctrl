from argparse import Namespace
from typing import Self

from v3xctrl_helper import apply_expo, clamp

from .Mixer import Mixer, esc_pulse_width, map_range


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
        center = (self._steering_max + self._steering_min) / 2 + (self._steering_trim * self._trim_multiplier)

        return self._throttle_idle, int(clamp(center, self._steering_min, self._steering_max))

    @property
    def failsafe(self) -> tuple[int, int]:
        return self._throttle_failsafe, self._steering_failsafe

    def adjust_trim(self, step: int) -> tuple[str, int]:
        self._steering_trim += step

        return ".control.mixer.ackermann.steering.trim", self._steering_trim
