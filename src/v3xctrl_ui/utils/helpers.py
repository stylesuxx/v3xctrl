from collections import deque
import io
import logging
import time
from typing import Tuple, Dict
import pygame
from pygame.freetype import Font

import urllib.request
from material_icons import MaterialIcons, IconStyle

from v3xctrl_helper import clamp, color_to_hex


_icon_cache: Dict[Tuple, pygame.Surface] = {}
_mask_cache: Dict[Tuple[int, int, int, int], pygame.Surface] = {}


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
    """
    Apply rounded corners to a pygame surface with anti-aliasing.

    The rounded corner mask is cached based on surface dimensions, radius, and scale
    to avoid expensive smoothscale operations on repeated calls.

    Args:
        surface: The surface to apply rounded corners to
        radius: Corner radius in pixels
        scale: Anti-aliasing scale factor (2 = 2x upscale for smoother edges)

    Returns:
        New surface with rounded corners applied
    """
    width, height = surface.get_size()
    cache_key = (width, height, radius, scale)

    # Re-use cached mask if possible
    if cache_key not in _mask_cache:
        mask_large = pygame.Surface((width * scale, height * scale), pygame.SRCALPHA)
        pygame.draw.rect(
            mask_large,
            (255, 255, 255, 255),
            (0, 0, width * scale, height * scale),
            border_radius=radius * scale
        )
        mask = pygame.transform.smoothscale(mask_large, (width, height))
        _mask_cache[cache_key] = mask
    else:
        mask = _mask_cache[cache_key]

    # Apply the mask to the surface
    rounded = pygame.Surface((width, height), pygame.SRCALPHA)
    rounded.blit(surface, (0, 0))
    rounded.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    return rounded


def render_text_full_height(
    font: Font,
    text: str,
    color: Tuple[int, int, int]
) -> pygame.Surface:
    text_surface, rect = font.render(text, color)

    ascent = font.get_sized_ascender()
    descent = font.get_sized_descender()
    full_height = ascent - descent

    full_surface = pygame.Surface((text_surface.get_width(), full_height), pygame.SRCALPHA)

    # Position so baseline is at 'ascent' pixels from top
    y_offset = ascent - rect.y

    full_surface.blit(text_surface, (0, y_offset))

    return full_surface


def calculate_widget_position(
    alignment: str,
    widget_width: int,
    widget_height: int,
    screen_width: int,
    screen_height: int,
    offset: Tuple[int, int] = (0, 0)
) -> Tuple[int, int]:
    """Calculate widget position based on alignment and offset.

    Offset is always relative to the alignment point:
    - top-left: offset is from (top, left)
    - top-right: offset is from (top, right)
    - bottom-left: offset is from (bottom, left)
    - bottom-right: offset is from (bottom, right)
    - bottom-center: offset is from (bottom, center)
    """
    if alignment == "top-left":
        return offset

    elif alignment == "top-right":
        position = (screen_width, 0)
        position = (position[0] - offset[1] - widget_width, position[1] + offset[0])

        return position

    elif alignment == "bottom-left":
        position = (0, screen_height)
        position = (position[0] + offset[1], position[1] - offset[0] - widget_height)

        return position

    elif alignment == "bottom-right":
        position = (screen_width, screen_height)
        position = (position[0] - offset[1] - widget_width, position[1] - offset[0] - widget_height)

        return position

    elif alignment == "bottom-center":
        position = (screen_width // 2, screen_height)
        position = (position[0] - offset[1] - (widget_width // 2), position[1] - offset[0] - widget_height)

        return position

    return (0, 0)
