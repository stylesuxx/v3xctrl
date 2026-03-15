import io
import logging
import time
import urllib.request
from collections import deque

import pygame
from material_icons import IconStyle, MaterialIcons
from pygame.freetype import Font

from v3xctrl_helper import clamp, color_to_hex

logger = logging.getLogger(__name__)

_icon_cache: dict[tuple[str, int, tuple[int, int, int], IconStyle, int], pygame.Surface] = {}
_mask_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}


def _interpolate_color(value: float) -> tuple[int, int, int]:
    """Interpolate blue -> green -> red for a value in [0, 1]."""
    if value <= 0.5:
        t = value / 0.5
        return (0, int(t * 255), int((1 - t) * 255))
    else:
        t = (value - 0.5) / 0.5
        return (int(t * 255), int((1 - t) * 255), 0)


def interpolate_steering_color(steering: float) -> tuple[int, int, int]:
    return _interpolate_color(clamp(abs(steering), 0.0, 1.0))


def interpolate_throttle_color(throttle: float) -> tuple[int, int, int]:
    return _interpolate_color(clamp(throttle, 0.0, 1.0))


def get_fps(history: deque[float], window_seconds: float = 1) -> int:
    now = time.monotonic()
    cutoff = now - window_seconds
    frames = [t for t in history if t >= cutoff]

    return int(len(frames) / window_seconds) if frames else 0


def get_external_ip(timeout: int = 5) -> str:
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=timeout) as response:
            return response.read().decode("utf-8")
    except Exception:
        logger.warning("Could not get external IP address")
        return "0.0.0.0"


def get_icon(
    name: str,
    size: int = 24,
    color: tuple[int, int, int] = (0, 0, 0),
    style: IconStyle = IconStyle.ROUND,
    rotation: int = 0,
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


def round_corners(surface: pygame.Surface, radius: int, scale: int = 2) -> pygame.Surface:
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

    if cache_key in _mask_cache:
        mask = _mask_cache[cache_key]
    else:
        mask_large = pygame.Surface((width * scale, height * scale), pygame.SRCALPHA)
        pygame.draw.rect(
            mask_large, (255, 255, 255, 255), (0, 0, width * scale, height * scale), border_radius=radius * scale
        )
        mask = pygame.transform.smoothscale(mask_large, (width, height))
        _mask_cache[cache_key] = mask

    rounded = pygame.Surface((width, height), pygame.SRCALPHA)
    rounded.blit(surface, (0, 0))
    rounded.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    return rounded


def render_text_full_height(font: Font, text: str, color: tuple[int, int, int]) -> pygame.Surface:
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
    offset: tuple[int, int] = (0, 0),
) -> tuple[int, int]:
    match alignment:
        case "top-left":
            return offset

        case "top-right":
            return (screen_width - offset[1] - widget_width, offset[0])

        case "bottom-left":
            return (offset[1], screen_height - offset[0] - widget_height)

        case "bottom-right":
            return (screen_width - offset[1] - widget_width, screen_height - offset[0] - widget_height)

        case "bottom-center":
            return (screen_width // 2 - offset[1] - widget_width // 2, screen_height - offset[0] - widget_height)

        case _:
            return (0, 0)
