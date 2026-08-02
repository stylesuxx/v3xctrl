from enum import StrEnum

from v3xctrl_helper import clamp


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
