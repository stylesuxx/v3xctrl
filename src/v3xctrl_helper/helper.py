import math

EARTH_RADIUS_METERS = 6_371_000.0


def clamp(raw: float, min_val: float, max_val: float) -> float:
    lower = min(min_val, max_val)
    upper = max(min_val, max_val)
    clamped = max(lower, min(upper, raw))

    return clamped


def color_to_hex(color: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{c:02X}" for c in color)


def apply_expo(value: float, expo: int) -> float:
    if expo == 0:
        return value

    exponent = 1.0 + (expo / 100.0) * 4.0
    return math.copysign(abs(value) ** exponent, value)


def is_int(number: str) -> bool:
    try:
        int(number)
        return True

    except ValueError:
        return False


def haversine_meters(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Great-circle distance, treating the earth as a sphere - under 0.5% off, fine at GPS noise."""
    phi_a = math.radians(lat_a)
    phi_b = math.radians(lat_b)
    delta_phi = math.radians(lat_b - lat_a)
    delta_lambda = math.radians(lon_b - lon_a)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2

    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))
