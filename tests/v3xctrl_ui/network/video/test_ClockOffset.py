import unittest

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
        # T1=1.0, T2=1.005, T4=1.010
        # offset = 1.005 - (1.0 + 1.010) / 2 = 1.005 - 1.005 = 0
        offset.update(viewer_send=1.0, streamer_timestamp=1.005, viewer_receive=1.010)

        self.assertEqual(offset.offset_us, 0)

    def test_positive_offset_when_streamer_ahead(self):
        offset = ClockOffset()

        # Streamer clock is 1ms ahead
        # T1=1.0, T2=1.006, T4=1.010
        # offset = 1.006 - 1.005 = 0.001 = 1000us
        offset.update(viewer_send=1.0, streamer_timestamp=1.006, viewer_receive=1.010)

        self.assertEqual(offset.offset_us, 1000)

    def test_negative_offset_when_streamer_behind(self):
        offset = ClockOffset()

        # Streamer clock is 2ms behind
        # T1=1.0, T2=1.003, T4=1.010
        # offset = 1.003 - 1.005 = -0.002 = -2000us
        offset.update(viewer_send=1.0, streamer_timestamp=1.003, viewer_receive=1.010)

        self.assertEqual(offset.offset_us, -2000)

    def test_rtt_calculated(self):
        offset = ClockOffset()

        offset.update(viewer_send=1.0, streamer_timestamp=1.005, viewer_receive=1.010)

        self.assertAlmostEqual(offset.rtt, 0.010)

    def test_update_overwrites_previous(self):
        offset = ClockOffset()

        offset.update(viewer_send=1.0, streamer_timestamp=1.006, viewer_receive=1.010)
        self.assertEqual(offset.offset_us, 1000)

        offset.update(viewer_send=2.0, streamer_timestamp=2.005, viewer_receive=2.010)
        self.assertEqual(offset.offset_us, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
