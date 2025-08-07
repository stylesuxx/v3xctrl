def clamp(raw: float, min_val: float, max_val: float) -> float:
    lower = min(min_val, max_val)
    upper = max(min_val, max_val)
    clamped = max(lower, min(upper, raw))

    return clamped
