from v3xctrl_ui.helpers import interpolate_steering_color


def test_interpolate_steering_color():
    assert interpolate_steering_color(0) == (0, 0, 255)
    assert interpolate_steering_color(0.5) == (0, 255, 0)
    assert interpolate_steering_color(1.0) == (255, 0, 0)
    assert interpolate_steering_color(-0.5) == (0, 255, 0)
    assert interpolate_steering_color(-1.0) == (255, 0, 0)
