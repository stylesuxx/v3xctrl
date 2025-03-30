from src.ui.helpers import clamp


def test_clamp():
    assert clamp(1, 0, 2) == 1
    assert clamp(10, 0, 2) == 2
    assert clamp(0.1, -1.0, 1.0) == 0.1
    assert clamp(1.1, -1.0, 1.0) == 1.0
    assert clamp(-2.0, -1.0, 1.0) == -1.0
    assert clamp(0.0, -1.0, 1.0) == 0.0
