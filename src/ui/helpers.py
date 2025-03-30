from typing import Tuple


def clamp(val, min_val, max_val):
    return max(min(val, max_val), min_val)


def interpolate_steering_color(steering: float) -> Tuple[int, int, int]:
    value = clamp(abs(steering), 0.0, 1.0)

    if value <= 0.5:
        # Blue to Green
        t = value / 0.5  # [0, 0.5] → [0, 1]
        r = 0
        g = int(t * 255)
        b = int((1 - t) * 255)
    else:
        # Green to Red
        t = (value - 0.5) / 0.5  # [0.5, 1] → [0, 1]
        r = int(t * 255)
        g = int((1 - t) * 255)
        b = 0

    return (r, g, b)


def interpolate_throttle_color(throttle: float) -> Tuple[int, int, int]:
    value = clamp(throttle, 0.0, 1.0)

    if value <= 0.5:
        # Blue to Green
        factor = value / 0.5
        r = 0
        g = int(factor * 255)
        b = int((1 - factor) * 255)
    else:
        # Green to Red
        factor = (value - 0.5) / 0.5
        r = int(factor * 255)
        g = int((1 - factor) * 255)
        b = 0

    return (r, g, b)
