import unittest

from v3xctrl_helper.helper import apply_expo


class TestApplyExpo(unittest.TestCase):
    def test_expo_zero_returns_input_unchanged(self):
        self.assertEqual(apply_expo(0.5, 0), 0.5)
        self.assertEqual(apply_expo(-0.7, 0), -0.7)
        self.assertEqual(apply_expo(1.0, 0), 1.0)

    def test_zero_input_returns_zero(self):
        self.assertEqual(apply_expo(0.0, 0), 0.0)
        self.assertEqual(apply_expo(0.0, 50), 0.0)
        self.assertEqual(apply_expo(0.0, 100), 0.0)

    def test_positive_endpoint_preserved(self):
        self.assertAlmostEqual(apply_expo(1.0, 0), 1.0)
        self.assertAlmostEqual(apply_expo(1.0, 50), 1.0)
        self.assertAlmostEqual(apply_expo(1.0, 100), 1.0)

    def test_negative_endpoint_preserved(self):
        self.assertAlmostEqual(apply_expo(-1.0, 0), -1.0)
        self.assertAlmostEqual(apply_expo(-1.0, 50), -1.0)
        self.assertAlmostEqual(apply_expo(-1.0, 100), -1.0)

    def test_symmetry(self):
        for expo in [10, 30, 50, 75, 100]:
            for value in [0.1, 0.3, 0.5, 0.7, 0.9]:
                with self.subTest(expo=expo, value=value):
                    self.assertAlmostEqual(
                        apply_expo(-value, expo),
                        -apply_expo(value, expo),
                    )

    def test_max_expo_is_fifth_power(self):
        self.assertAlmostEqual(apply_expo(0.5, 100), 0.5**5)
        self.assertAlmostEqual(apply_expo(0.8, 100), 0.8**5)

    def test_mid_expo_is_cubic(self):
        self.assertAlmostEqual(apply_expo(0.5, 50), 0.5**3)
        self.assertAlmostEqual(apply_expo(0.8, 50), 0.8**3)

    def test_expo_attenuates_center(self):
        linear_value = 0.3
        for expo in [10, 30, 50, 75, 100]:
            with self.subTest(expo=expo):
                result = apply_expo(linear_value, expo)
                self.assertLess(abs(result), abs(linear_value))

    def test_higher_expo_attenuates_more(self):
        value = 0.5
        previous = value
        for expo in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            result = apply_expo(value, expo)
            self.assertLess(result, previous)
            previous = result


if __name__ == "__main__":
    unittest.main()
