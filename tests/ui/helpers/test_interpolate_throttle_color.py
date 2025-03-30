from src.ui.helpers import interpolate_throttle_color


def test_interpolate_throttle_color():
    assert interpolate_throttle_color(0) == (0, 0, 255)
    assert interpolate_throttle_color(0.5) == (0, 255, 0)
    assert interpolate_throttle_color(1.0) == (255, 0, 0)
    assert interpolate_throttle_color(-0.5) == (0, 0, 255)
    assert interpolate_throttle_color(-1.0) == (0, 0, 255)
