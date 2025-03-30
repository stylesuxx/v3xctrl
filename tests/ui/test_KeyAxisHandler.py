from pytest import approx

from src.ui.KeyAxisHandler import KeyAxisHandler


def test_positive_key_increases_value():
    handler = KeyAxisHandler(positive=1, negative=2, step=0.1)
    keys = [False] * 10
    keys[1] = True

    handler.update(keys)

    assert handler.value == 0.1


def test_friction_applies_when_no_keys_pressed():
    handler = KeyAxisHandler(positive=1, negative=2, step=0.1, friction=0.05)
    handler.value = 0.2
    keys = [False] * 10

    handler.update(keys)

    assert handler.value == approx(0.15)
