from typing import Tuple


def clamp(raw: float, min_val: float, max_val: float) -> float:
    lower = min(min_val, max_val)
    upper = max(min_val, max_val)
    clamped = max(lower, min(upper, raw))

    return clamped


def color_to_hex(color: Tuple[int, int, int]) -> str:
    return "#" + "".join(f"{c:02X}" for c in color)


def is_int(number: str) -> bool:
    try:
        int(number)
        return True

    except ValueError:
        return False
