from typing import Tuple


def clamp(raw: float, min_val: float, max_val: float) -> float:
    lower = min(min_val, max_val)
    upper = max(min_val, max_val)
    clamped = max(lower, min(upper, raw))

    return clamped


def color_to_hex(color: Tuple[int, int, int]) -> str:
    hex_color = "#"
    for item in color:
        hex_color += hex(item)[2:].upper().zfill(2)

    return hex_color
