import unittest
from unittest.mock import patch

from v3xctrl_helper import SlidingWindowAverage


class TestSlidingWindowAverage(unittest.TestCase):
    def test_empty_average_is_zero(self):
        window = SlidingWindowAverage(window_seconds=5.0)

        self.assertEqual(window.average, 0.0)

    def test_empty_is_falsy(self):
        window = SlidingWindowAverage(window_seconds=5.0)

        self.assertFalse(window)
        self.assertEqual(len(window), 0)

    def test_single_sample(self):
        window = SlidingWindowAverage(window_seconds=5.0)

        window.append(42.0)

        self.assertEqual(window.average, 42.0)
        self.assertTrue(window)
        self.assertEqual(len(window), 1)

    def test_averages_multiple_samples(self):
        window = SlidingWindowAverage(window_seconds=10.0)
        monotonic = 100.0

        with patch("v3xctrl_helper.SlidingWindowAverage.time") as mock_time:
            mock_time.monotonic.return_value = monotonic
            window.append(10.0)

            mock_time.monotonic.return_value = monotonic + 1
            window.append(20.0)

            mock_time.monotonic.return_value = monotonic + 2
            window.append(30.0)

        self.assertEqual(window.average, 20.0)
        self.assertEqual(len(window), 3)

    def test_evicts_old_samples(self):
        window = SlidingWindowAverage(window_seconds=3.0)
        monotonic = 100.0

        with patch("v3xctrl_helper.SlidingWindowAverage.time") as mock_time:
            mock_time.monotonic.return_value = monotonic
            window.append(100.0)

            mock_time.monotonic.return_value = monotonic + 4
            window.append(50.0)

        self.assertEqual(window.average, 50.0)
        self.assertEqual(len(window), 1)

    def test_clear(self):
        window = SlidingWindowAverage(window_seconds=5.0)

        window.append(1.0)
        window.append(2.0)
        window.clear()

        self.assertEqual(len(window), 0)
        self.assertFalse(window)
        self.assertEqual(window.average, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
