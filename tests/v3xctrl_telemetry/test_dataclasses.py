import unittest

from v3xctrl_telemetry.dataclasses import (
    GstFlags,
    ServiceFlags,
    ThrottleFlags,
    VideoCoreFlags,
)


class TestGstFlags(unittest.TestCase):
    def test_default_values(self):
        flags = GstFlags()
        self.assertFalse(flags.recording)
        self.assertFalse(flags.udp_overrun)

    def test_to_byte_no_flags(self):
        self.assertEqual(GstFlags().to_byte(), 0)

    def test_to_byte_recording(self):
        self.assertEqual(GstFlags(recording=True).to_byte(), 0b01)

    def test_to_byte_udp_overrun(self):
        self.assertEqual(GstFlags(udp_overrun=True).to_byte(), 0b10)

    def test_to_byte_all_flags(self):
        self.assertEqual(GstFlags(recording=True, udp_overrun=True).to_byte(), 0b11)

    def test_from_byte_no_flags(self):
        flags = GstFlags.from_byte(0)
        self.assertFalse(flags.recording)
        self.assertFalse(flags.udp_overrun)

    def test_from_byte_recording(self):
        flags = GstFlags.from_byte(0b01)
        self.assertTrue(flags.recording)
        self.assertFalse(flags.udp_overrun)

    def test_from_byte_udp_overrun(self):
        flags = GstFlags.from_byte(0b10)
        self.assertFalse(flags.recording)
        self.assertTrue(flags.udp_overrun)

    def test_from_byte_all_flags(self):
        flags = GstFlags.from_byte(0b11)
        self.assertTrue(flags.recording)
        self.assertTrue(flags.udp_overrun)

    def test_round_trip(self):
        for recording in (True, False):
            for udp_overrun in (True, False):
                original = GstFlags(recording=recording, udp_overrun=udp_overrun)
                restored = GstFlags.from_byte(original.to_byte())
                self.assertEqual(original, restored)


class TestServiceFlags(unittest.TestCase):
    def test_default_values(self):
        flags = ServiceFlags()
        self.assertFalse(flags.video)
        self.assertFalse(flags.reverse_shell)
        self.assertFalse(flags.debug)

    def test_to_byte_no_flags(self):
        self.assertEqual(ServiceFlags().to_byte(), 0)

    def test_to_byte_video(self):
        self.assertEqual(ServiceFlags(video=True).to_byte(), 0b001)

    def test_to_byte_reverse_shell(self):
        self.assertEqual(ServiceFlags(reverse_shell=True).to_byte(), 0b010)

    def test_to_byte_debug(self):
        self.assertEqual(ServiceFlags(debug=True).to_byte(), 0b100)

    def test_to_byte_all_flags(self):
        flags = ServiceFlags(video=True, reverse_shell=True, debug=True)
        self.assertEqual(flags.to_byte(), 0b111)

    def test_from_byte_no_flags(self):
        flags = ServiceFlags.from_byte(0)
        self.assertFalse(flags.video)
        self.assertFalse(flags.reverse_shell)
        self.assertFalse(flags.debug)

    def test_from_byte_video(self):
        flags = ServiceFlags.from_byte(0b001)
        self.assertTrue(flags.video)
        self.assertFalse(flags.reverse_shell)
        self.assertFalse(flags.debug)

    def test_from_byte_all_flags(self):
        flags = ServiceFlags.from_byte(0b111)
        self.assertTrue(flags.video)
        self.assertTrue(flags.reverse_shell)
        self.assertTrue(flags.debug)

    def test_round_trip(self):
        for video in (True, False):
            for reverse_shell in (True, False):
                for debug in (True, False):
                    original = ServiceFlags(video=video, reverse_shell=reverse_shell, debug=debug)
                    restored = ServiceFlags.from_byte(original.to_byte())
                    self.assertEqual(original, restored)


class TestThrottleFlags(unittest.TestCase):
    def test_default_values(self):
        flags = ThrottleFlags()
        self.assertFalse(flags.undervolt)
        self.assertFalse(flags.freq_capped)
        self.assertFalse(flags.throttled)
        self.assertFalse(flags.soft_temp_limit)

    def test_to_nibble_no_flags(self):
        self.assertEqual(ThrottleFlags().to_nibble(), 0)

    def test_to_nibble_undervolt(self):
        self.assertEqual(ThrottleFlags(undervolt=True).to_nibble(), 0b0001)

    def test_to_nibble_freq_capped(self):
        self.assertEqual(ThrottleFlags(freq_capped=True).to_nibble(), 0b0010)

    def test_to_nibble_throttled(self):
        self.assertEqual(ThrottleFlags(throttled=True).to_nibble(), 0b0100)

    def test_to_nibble_soft_temp_limit(self):
        self.assertEqual(ThrottleFlags(soft_temp_limit=True).to_nibble(), 0b1000)

    def test_to_nibble_all_flags(self):
        flags = ThrottleFlags(undervolt=True, freq_capped=True, throttled=True, soft_temp_limit=True)
        self.assertEqual(flags.to_nibble(), 0b1111)

    def test_from_nibble_no_flags(self):
        flags = ThrottleFlags.from_nibble(0)
        self.assertFalse(flags.undervolt)
        self.assertFalse(flags.freq_capped)
        self.assertFalse(flags.throttled)
        self.assertFalse(flags.soft_temp_limit)

    def test_from_nibble_undervolt(self):
        flags = ThrottleFlags.from_nibble(0b0001)
        self.assertTrue(flags.undervolt)
        self.assertFalse(flags.freq_capped)

    def test_from_nibble_all_flags(self):
        flags = ThrottleFlags.from_nibble(0b1111)
        self.assertTrue(flags.undervolt)
        self.assertTrue(flags.freq_capped)
        self.assertTrue(flags.throttled)
        self.assertTrue(flags.soft_temp_limit)

    def test_round_trip(self):
        for value in range(16):
            flags = ThrottleFlags.from_nibble(value)
            self.assertEqual(flags.to_nibble(), value)

    def test_nibble_stays_within_4_bits(self):
        flags = ThrottleFlags(undervolt=True, freq_capped=True, throttled=True, soft_temp_limit=True)
        self.assertLessEqual(flags.to_nibble(), 0x0F)


class TestVideoCoreFlags(unittest.TestCase):
    def test_default_values(self):
        flags = VideoCoreFlags()
        self.assertIsNotNone(flags.current)
        self.assertIsNotNone(flags.history)
        self.assertFalse(flags.current.undervolt)
        self.assertFalse(flags.history.undervolt)

    def test_post_init_creates_throttle_flags(self):
        flags = VideoCoreFlags()
        self.assertIsInstance(flags.current, ThrottleFlags)
        self.assertIsInstance(flags.history, ThrottleFlags)

    def test_post_init_preserves_explicit_values(self):
        current = ThrottleFlags(undervolt=True)
        history = ThrottleFlags(throttled=True)
        flags = VideoCoreFlags(current=current, history=history)
        self.assertTrue(flags.current.undervolt)
        self.assertTrue(flags.history.throttled)

    def test_to_byte_no_flags(self):
        self.assertEqual(VideoCoreFlags().to_byte(), 0x00)

    def test_to_byte_current_only(self):
        current = ThrottleFlags(undervolt=True, throttled=True)
        flags = VideoCoreFlags(current=current)
        self.assertEqual(flags.to_byte(), 0x05)

    def test_to_byte_history_only(self):
        history = ThrottleFlags(undervolt=True, throttled=True)
        flags = VideoCoreFlags(history=history)
        self.assertEqual(flags.to_byte(), 0x50)

    def test_to_byte_both(self):
        current = ThrottleFlags(undervolt=True)
        history = ThrottleFlags(freq_capped=True)
        flags = VideoCoreFlags(current=current, history=history)
        self.assertEqual(flags.to_byte(), 0x21)

    def test_to_byte_all_flags(self):
        current = ThrottleFlags(undervolt=True, freq_capped=True, throttled=True, soft_temp_limit=True)
        history = ThrottleFlags(undervolt=True, freq_capped=True, throttled=True, soft_temp_limit=True)
        flags = VideoCoreFlags(current=current, history=history)
        self.assertEqual(flags.to_byte(), 0xFF)

    def test_from_byte_no_flags(self):
        flags = VideoCoreFlags.from_byte(0x00)
        self.assertFalse(flags.current.undervolt)
        self.assertFalse(flags.history.undervolt)

    def test_from_byte_current_only(self):
        flags = VideoCoreFlags.from_byte(0x05)
        self.assertTrue(flags.current.undervolt)
        self.assertTrue(flags.current.throttled)
        self.assertFalse(flags.history.undervolt)

    def test_from_byte_history_only(self):
        flags = VideoCoreFlags.from_byte(0x50)
        self.assertFalse(flags.current.undervolt)
        self.assertTrue(flags.history.undervolt)
        self.assertTrue(flags.history.throttled)

    def test_from_byte_all_flags(self):
        flags = VideoCoreFlags.from_byte(0xFF)
        self.assertTrue(flags.current.undervolt)
        self.assertTrue(flags.current.freq_capped)
        self.assertTrue(flags.current.throttled)
        self.assertTrue(flags.current.soft_temp_limit)
        self.assertTrue(flags.history.undervolt)
        self.assertTrue(flags.history.freq_capped)
        self.assertTrue(flags.history.throttled)
        self.assertTrue(flags.history.soft_temp_limit)

    def test_round_trip(self):
        for value in range(256):
            flags = VideoCoreFlags.from_byte(value)
            self.assertEqual(flags.to_byte(), value)

    def test_lower_nibble_is_current_upper_is_history(self):
        flags = VideoCoreFlags.from_byte(0xA5)
        self.assertEqual(flags.current.to_nibble(), 0x5)
        self.assertEqual(flags.history.to_nibble(), 0xA)


if __name__ == "__main__":
    unittest.main()
