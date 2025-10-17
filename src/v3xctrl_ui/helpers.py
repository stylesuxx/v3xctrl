from collections import deque
import io
import logging
import time
from typing import Tuple, Dict
import pygame

import urllib.request
from material_icons import MaterialIcons, IconStyle

from v3xctrl_helper import clamp, color_to_hex


_icon_cache: Dict[Tuple, pygame.Surface] = {}


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


def get_fps(history: deque[float], window_seconds: float = 1) -> int:
    now = time.monotonic()
    cutoff = now - window_seconds
    frames = [t for t in history if t >= cutoff]
    return int(len(frames) / window_seconds) if frames else 0


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
    style: IconStyle = IconStyle.ROUND,
    rotation: int = 0
) -> pygame.Surface:
    """
    Get a Material Design icon as a pygame surface.
    Results are cached to avoid repeated loading of the same icons.
    """
    cache_key = (name, size, color, style, rotation)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    icons = MaterialIcons()
    hex_color = color_to_hex(color)
    icon = icons.get(name, size=size, color=hex_color, style=style)
    surface = pygame.image.load(io.BytesIO(icon))

    if rotation != 0:
        surface = pygame.transform.rotate(surface, rotation)

    _icon_cache[cache_key] = surface

    return surface


def round_corners(
    surface: pygame.Surface,
    radius: int,
    scale: int = 2
) -> pygame.Surface:
    width, height = surface.get_size()

    # Scale and transform mask for anti-alias
    mask_large = pygame.Surface((width * scale, height * scale), pygame.SRCALPHA)
    pygame.draw.rect(
        mask_large,
        (255, 255, 255, 255),
        (0, 0, width * scale, height * scale),
        border_radius=radius * scale
    )
    mask = pygame.transform.smoothscale(mask_large, (width, height))

    rounded = pygame.Surface((width, height), pygame.SRCALPHA)
    rounded.blit(surface, (0, 0))
    rounded.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    return rounded
