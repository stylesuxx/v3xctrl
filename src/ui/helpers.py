import time
from typing import Tuple
import urllib.request


def clamp(value, min_value, max_value):
    return max(min(value, max_value), min_value)


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


def get_fps(history, window_seconds: float = 1):
    now = time.time()
    cutoff = now - window_seconds
    frames = [t for t in history if t >= cutoff]
    return len(frames) / window_seconds if frames else 0.0


def get_external_ip():
    with urllib.request.urlopen('https://api.ipify.org') as response:
        return response.read().decode('utf-8')
