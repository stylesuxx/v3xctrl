import unittest
from unittest.mock import patch

from v3xctrl_ui.network.video.ClockOffset import ClockOffset


class TestClockOffset(unittest.TestCase):
    def test_initially_invalid(self):
        offset = ClockOffset()

        self.assertFalse(offset.valid)
        self.assertEqual(offset.offset_us, 0)
        self.assertEqual(offset.rtt, 0.0)

    def test_becomes_valid_after_update(self):
        offset = ClockOffset()

        offset.update(viewer_send=1.0, streamer_timestamp=1.005, viewer_receive=1.010)

        self.assertTrue(offset.valid)

    def test_zero_offset_when_clocks_synced(self):
        offset = ClockOffset()

        # Symmetric 10ms RTT, clocks perfectly synced
        # offset = 1.005 - (1.0 + 1.010) / 2 = 0
        offset.update(viewer_send=1.0, streamer_timestamp=1.005, viewer_receive=1.010)

        self.assertEqual(offset.offset_us, 0)

    def test_positive_offset_when_streamer_ahead(self):
        offset = ClockOffset()

        # Streamer clock is 1ms ahead
        # offset = 1.006 - 1.005 = 0.001 = 1000us
        offset.update(viewer_send=1.0, streamer_timestamp=1.006, viewer_receive=1.010)

        self.assertEqual(offset.offset_us, 1000)

    def test_negative_offset_when_streamer_behind(self):
        offset = ClockOffset()

        # Streamer clock is 2ms behind
        # offset = 1.003 - 1.005 = -0.002 = -2000us
        offset.update(viewer_send=1.0, streamer_timestamp=1.003, viewer_receive=1.010)

        self.assertEqual(offset.offset_us, -2000)

    def test_rtt_calculated(self):
        offset = ClockOffset()

        offset.update(viewer_send=1.0, streamer_timestamp=1.005, viewer_receive=1.010)

        self.assertAlmostEqual(offset.rtt, 0.010)

    def test_averages_multiple_samples(self):
        offset = ClockOffset(window_seconds=10.0)
        monotonic = 100.0

        with patch("v3xctrl_helper.SlidingWindowAverage.time") as mock_time:
            # Three measurements: 1000, 2000, 3000 us offset
            mock_time.monotonic.return_value = monotonic
            offset.update(viewer_send=1.0, streamer_timestamp=1.006, viewer_receive=1.010)  # 1000us

            mock_time.monotonic.return_value = monotonic + 1
            offset.update(viewer_send=2.0, streamer_timestamp=2.007, viewer_receive=2.010)  # 2000us

            mock_time.monotonic.return_value = monotonic + 2
            offset.update(viewer_send=3.0, streamer_timestamp=3.008, viewer_receive=3.010)  # 3000us

        self.assertEqual(offset.offset_us, 2000)

    def test_evicts_samples_outside_window(self):
        offset = ClockOffset(window_seconds=3.0)
        monotonic = 100.0

        with patch("v3xctrl_helper.SlidingWindowAverage.time") as mock_time:
            mock_time.monotonic.return_value = monotonic
            offset.update(viewer_send=1.0, streamer_timestamp=1.010, viewer_receive=1.010)  # 5000us

            mock_time.monotonic.return_value = monotonic + 4
            offset.update(viewer_send=2.0, streamer_timestamp=2.005, viewer_receive=2.010)  # 0us

        # First sample (5000us) should be evicted, only 0us remains
        self.assertEqual(offset.offset_us, 0)
        self.assertEqual(len(offset._samples), 1)

    def test_single_sample_no_averaging(self):
        offset = ClockOffset()

        offset.update(viewer_send=1.0, streamer_timestamp=1.006, viewer_receive=1.010)

        self.assertEqual(offset.offset_us, 1000)

    def test_default_window_is_three_seconds(self):
        offset = ClockOffset()

        self.assertEqual(offset._samples._window_seconds, 3.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
