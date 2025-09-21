from collections import deque
import io
import logging
import time
from typing import Tuple
import pygame

import urllib.request
from material_icons import MaterialIcons, IconStyle

from v3xctrl_helper import clamp, color_to_hex


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


def get_fps(history: deque[float], window_seconds: float = 1) -> float:
    now = time.monotonic()
    cutoff = now - window_seconds
    frames = [t for t in history if t >= cutoff]
    return len(frames) / window_seconds if frames else 0.0


def get_external_ip(timeout: int = 5) -> str:
    try:
        with urllib.request.urlopen('https://api.ipify.org', timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception:
        logging.warning("Could not get external IP address")
        return "0.0.0.0"


def get_icon(
    name: str,
    size: int = 24,
    color: Tuple[int, int, int] = (0, 0, 0),
    style: IconStyle = IconStyle.ROUND
) -> pygame.Surface:
    icons = MaterialIcons()
    hex_color = color_to_hex(color)
    icon = icons.get(name, size=size, color=hex_color, style=style)

    return pygame.image.load(io.BytesIO(icon))
