import unittest
from v3xctrl_ui.KeyAxisHandler import KeyAxisHandler


def mock_keys(pressed_indices, total=300):
    """Returns a list of bools simulating pygame key state."""
    keys = [False] * total
    for index in pressed_indices:
        keys[index] = True
    return keys


class TestKeyAxisHandler(unittest.TestCase):

    def test_positive_key_increases_value(self):
        handler = KeyAxisHandler(positive=1, negative=2, step=0.1)
        keys = mock_keys([1])
        handler.update(keys)
        self.assertAlmostEqual(handler.value, 0.05)

    def test_negative_key_decreases_value(self):
        handler = KeyAxisHandler(positive=1, negative=2, step=0.1)
        keys = mock_keys([2])
        handler.update(keys)
        self.assertAlmostEqual(handler.value, -0.05)

    def test_no_keys_applies_friction(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.05)
        handler.value = 0.2
        keys = mock_keys([])
        handler.update(keys)
        self.assertAlmostEqual(handler.value, 0.19)

    def test_friction_zeroes_small_values(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.05)
        handler.value = 0.038
        keys = mock_keys([])
        handler.update(keys)
        self.assertEqual(handler.value, 0.0361)

    def test_value_clamps_to_max(self):
        handler = KeyAxisHandler(positive=1, negative=2, step=1.0, max_val=0.5)
        keys = mock_keys([1])
        handler.update(keys)
        self.assertEqual(handler.value, 0.05)

    def test_value_clamps_to_min(self):
        handler = KeyAxisHandler(positive=1, negative=2, step=1.0, min_val=-0.5)
        keys = mock_keys([2])
        handler.update(keys)
        self.assertEqual(handler.value, -0.05)

    def test_deadzone_zeroes_small_values(self):
        handler = KeyAxisHandler(positive=1, negative=2, step=0.1, deadzone=0.2)
        handler.value = 0.15
        keys = mock_keys([])
        handler.update(keys)
        self.assertEqual(handler.value, 0.0)

    def test_deadzone_retains_large_values(self):
        handler = KeyAxisHandler(positive=1, negative=2, step=0.1, deadzone=0.2)
        handler.value = 0.25
        keys = mock_keys([])
        handler.update(keys)
        self.assertNotEqual(handler.value, 0.0)


if __name__ == "__main__":
    unittest.main()
