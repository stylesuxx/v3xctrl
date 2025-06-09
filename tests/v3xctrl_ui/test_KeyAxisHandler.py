import unittest
from v3xctrl_ui.KeyAxisHandler import KeyAxisHandler


def mock_keys(pressed_indices, total=300):
    keys = [False] * total
    for index in pressed_indices:
        keys[index] = True
    return keys


class TestKeyAxisHandler(unittest.TestCase):

    def test_positive_key_increases_value(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.05)
        handler.frames_since_last_tap = 100  # ensure tap triggers
        keys = mock_keys([1])
        handler.update(keys)
        self.assertAlmostEqual(handler.value, 0.0)  # tap and friction cancel out at sweet spot

        # simulate a faster tap
        handler.frames_since_last_tap = 5
        handler.update(keys)
        self.assertGreater(handler.value, 0.0)

    def test_negative_key_decreases_value(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.05)
        handler.frames_since_last_tap = 100
        keys = mock_keys([2])
        handler.update(keys)
        self.assertAlmostEqual(handler.value, 0.0)

        handler.frames_since_last_tap = 5
        handler.update(keys)
        self.assertLess(handler.value, 0.0)

    def test_no_keys_applies_friction(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.05, centering_multiplier=2.0)
        handler.value = 0.2
        handler.cooldown = 0
        keys = mock_keys([])
        handler.update(keys)
        self.assertAlmostEqual(handler.value, 0.2 - (0.05 * 2.0))

    def test_friction_zeroes_small_values(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.02, deadzone=0.05, centering_multiplier=2.0)
        handler.value = 0.03
        handler.cooldown = 0
        keys = mock_keys([])
        handler.update(keys)
        self.assertEqual(handler.value, 0.0)

    def test_value_clamps_to_max(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.2, max_val=0.1)
        handler.frames_since_last_tap = 5
        keys = mock_keys([1])
        for _ in range(10):
            handler.update(keys)
        self.assertLessEqual(handler.value, 0.1)

    def test_value_clamps_to_min(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.2, min_val=-0.1)
        handler.frames_since_last_tap = 5
        keys = mock_keys([2])
        for _ in range(10):
            handler.update(keys)
        self.assertGreaterEqual(handler.value, -0.1)

    def test_deadzone_zeroes_small_values(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.01, deadzone=0.05, centering_multiplier=1.0)
        handler.value = 0.04
        handler.cooldown = 0
        keys = mock_keys([])
        handler.update(keys)
        self.assertEqual(handler.value, 0.0)

    def test_deadzone_retains_large_values(self):
        handler = KeyAxisHandler(positive=1, negative=2, friction=0.01, deadzone=0.05, centering_multiplier=1.0)
        handler.value = 0.061  # just above the threshold after decay
        handler.cooldown = 0
        keys = mock_keys([])
        handler.update(keys)
        self.assertNotEqual(handler.value, 0.0)


if __name__ == "__main__":
    unittest.main()
