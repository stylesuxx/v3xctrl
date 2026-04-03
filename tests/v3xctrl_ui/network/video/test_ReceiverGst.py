import sys
import time
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

import numpy as np

# Mock gi and GStreamer modules before any import of ReceiverGst.
# On environments without GStreamer installed, gi.require_version("Gst", "1.0")
# fails at module-level import time. Pre-populating sys.modules lets the import
# succeed with mocks instead.
_gi_mock = MagicMock()
_gst_mock = MagicMock()
_gstapp_mock = MagicMock()
_glib_mock = MagicMock()

# Set up Gst constants used by the production code
_gst_mock.CLOCK_TIME_NONE = -1
_gst_mock.SECOND = 1_000_000_000
_gst_mock.PadProbeReturn.OK = 0
_gst_mock.MapFlags.READ = 1

_modules_to_mock = {
    "gi": _gi_mock,
    "gi.repository": MagicMock(Gst=_gst_mock, GstApp=_gstapp_mock, GLib=_glib_mock),
}

# Only inject mocks for modules not already loaded (avoids clobbering real gi
# on machines that have GStreamer installed).
_patchers = {}
for mod_name, mock_obj in _modules_to_mock.items():
    if mod_name not in sys.modules:
        _patchers[mod_name] = mock_obj
        sys.modules[mod_name] = mock_obj

from v3xctrl_ui.network.video.ClockOffset import ClockOffset  # noqa: E402
from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst  # noqa: E402


def _make_receiver(**overrides) -> ReceiverGst:
    """Create a ReceiverGst instance without calling __init__."""
    receiver = ReceiverGst.__new__(ReceiverGst)
    defaults = {
        "max_age_seconds": 0.5,
        "latest_pts": None,
        "timeout_seconds": 5.0,
        "frame_lock": MagicMock(),
        "frame": None,
        "frame_buffer": deque(),
        "last_frame_time": 0.0,
        "pipeline": None,
        "appsink": None,
        "loop": None,
        "_receive_start_times": {},
        "_decode_start_times": {},
        "_receive_durations": {},
        "_timing_receive_samples": [],
        "_sei_timestamps": {},
        "_timing_e2e_samples": [],
        "_clock_offset": None,
        "timing_decode_samples": deque(maxlen=100),
        "timing_buffer_samples": deque(maxlen=100),
    }
    defaults.update(overrides)
    for attr, value in defaults.items():
        setattr(receiver, attr, value)
    return receiver


class TestShouldDropByAge(unittest.TestCase):
    def test_clock_time_none_is_not_dropped(self):
        receiver = _make_receiver()

        self.assertFalse(receiver._should_drop_by_age(_gst_mock.CLOCK_TIME_NONE))

    def test_first_frame_is_not_dropped(self):
        receiver = _make_receiver()

        self.assertFalse(receiver._should_drop_by_age(1_000_000_000))
        self.assertEqual(receiver.latest_pts, 1_000_000_000)

    def test_newer_frame_updates_latest_pts(self):
        receiver = _make_receiver(latest_pts=1_000_000_000)

        self.assertFalse(receiver._should_drop_by_age(2_000_000_000))
        self.assertEqual(receiver.latest_pts, 2_000_000_000)

    def test_slightly_older_frame_is_not_dropped(self):
        receiver = _make_receiver(latest_pts=2_000_000_000)

        # 100ms old - under 500ms threshold
        self.assertFalse(receiver._should_drop_by_age(1_900_000_000))

    def test_old_frame_is_dropped(self):
        receiver = _make_receiver(latest_pts=2_000_000_000)

        # 600ms old - over 500ms threshold
        self.assertTrue(receiver._should_drop_by_age(1_400_000_000))

    def test_frame_exactly_at_threshold_is_dropped(self):
        receiver = _make_receiver(latest_pts=2_000_000_000)

        # Exactly 500ms old
        self.assertTrue(receiver._should_drop_by_age(1_500_000_000))


class TestCheckTimeout(unittest.TestCase):
    def test_returns_true_when_no_frames_received(self):
        receiver = _make_receiver()

        self.assertTrue(receiver._check_timeout())

    def test_returns_true_when_not_timed_out(self):
        receiver = _make_receiver(last_frame_time=time.monotonic())

        self.assertTrue(receiver._check_timeout())
        self.assertIsNone(receiver.frame)

    def test_clears_frame_on_timeout(self):
        receiver = _make_receiver(
            last_frame_time=time.monotonic() - 10.0,
            frame=np.zeros((100, 100, 3), dtype=np.uint8),
            frame_buffer=deque([np.zeros((100, 100, 3), dtype=np.uint8)]),
        )

        receiver._check_timeout()

        self.assertIsNone(receiver.frame)
        self.assertEqual(len(receiver.frame_buffer), 0)

    def test_does_not_clear_when_already_none(self):
        receiver = _make_receiver(last_frame_time=time.monotonic() - 10.0)

        receiver._check_timeout()

        self.assertIsNone(receiver.frame)


class TestStopPipeline(unittest.TestCase):
    def test_cleanup_with_no_pipeline(self):
        receiver = _make_receiver()

        receiver._stop_pipeline()

        self.assertIsNone(receiver.pipeline)
        self.assertIsNone(receiver.appsink)
        self.assertIsNone(receiver.loop)

    def test_cleanup_stops_pipeline(self):
        mock_pipeline = MagicMock()
        receiver = _make_receiver(pipeline=mock_pipeline)

        receiver._stop_pipeline()

        mock_pipeline.set_state.assert_called_once()
        self.assertIsNone(receiver.pipeline)
        self.assertIsNone(receiver.appsink)

    def test_cleanup_quits_running_loop(self):
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        receiver = _make_receiver(loop=mock_loop)

        receiver._stop_pipeline()

        mock_loop.quit.assert_called_once()
        self.assertIsNone(receiver.loop)

    def test_cleanup_clears_timing_dicts(self):
        receiver = _make_receiver(
            _receive_start_times={1: 0.5, 2: 0.6},
            _decode_start_times={1: 0.7},
            _receive_durations={1: 0.1},
            _timing_receive_samples=[0.1, 0.2],
            _sei_timestamps={1: 100},
            _timing_e2e_samples=[0.05],
        )

        receiver._stop_pipeline()

        self.assertEqual(len(receiver._receive_start_times), 0)
        self.assertEqual(len(receiver._decode_start_times), 0)
        self.assertEqual(len(receiver._receive_durations), 0)
        self.assertEqual(len(receiver._timing_receive_samples), 0)
        self.assertEqual(len(receiver._sei_timestamps), 0)
        self.assertEqual(len(receiver._timing_e2e_samples), 0)


class TestLogTimingStats(unittest.TestCase):
    def test_no_output_when_empty(self):
        receiver = _make_receiver()

        with patch("v3xctrl_ui.network.video.ReceiverGst.logger") as mock_logger:
            receiver._log_timing_stats()

        mock_logger.debug.assert_not_called()

    def test_logs_timing_without_e2e(self):
        receiver = _make_receiver(
            _timing_receive_samples=[0.002, 0.003],
            _timing_e2e_samples=[],
        )
        receiver.timing_decode_samples.extend([0.005, 0.010])
        receiver.timing_buffer_samples.extend([0.020, 0.030])

        with patch("v3xctrl_ui.network.video.ReceiverGst.logger") as mock_logger:
            receiver._log_timing_stats()

        mock_logger.debug.assert_called_once()
        log_msg = mock_logger.debug.call_args[0][0]
        self.assertIn("[TIMING]", log_msg)
        self.assertIn("receive", log_msg)
        self.assertIn("decode", log_msg)
        self.assertIn("buffer", log_msg)
        self.assertIn("total", log_msg)
        self.assertNotIn("e2e", log_msg)

    def test_logs_timing_with_e2e(self):
        receiver = _make_receiver(
            _timing_receive_samples=[0.002],
            _timing_e2e_samples=[0.050, 0.060],
        )
        receiver.timing_decode_samples.extend([0.005])
        receiver.timing_buffer_samples.extend([0.020])

        with patch("v3xctrl_ui.network.video.ReceiverGst.logger") as mock_logger:
            receiver._log_timing_stats()

        log_msg = mock_logger.debug.call_args[0][0]
        self.assertIn("e2e", log_msg)

    def test_logs_clock_offset_when_valid(self):
        clock_offset = ClockOffset()
        clock_offset.update(1.0, 1.005, 1.010)
        receiver = _make_receiver(
            _timing_receive_samples=[0.002],
            _timing_e2e_samples=[0.050],
            _clock_offset=clock_offset,
        )
        receiver.timing_decode_samples.extend([0.005])
        receiver.timing_buffer_samples.extend([0.020])

        with patch("v3xctrl_ui.network.video.ReceiverGst.logger") as mock_logger:
            receiver._log_timing_stats()

        log_msg = mock_logger.debug.call_args[0][0]
        self.assertIn("clock-offset", log_msg)

    def test_no_clock_offset_when_not_set(self):
        receiver = _make_receiver(
            _timing_receive_samples=[0.002],
            _timing_e2e_samples=[],
        )
        receiver.timing_decode_samples.extend([0.005])
        receiver.timing_buffer_samples.extend([0.020])

        with patch("v3xctrl_ui.network.video.ReceiverGst.logger") as mock_logger:
            receiver._log_timing_stats()

        log_msg = mock_logger.debug.call_args[0][0]
        self.assertNotIn("clock-offset", log_msg)

    def test_clears_samples_after_logging(self):
        receiver = _make_receiver(
            _timing_receive_samples=[0.002],
            _timing_e2e_samples=[0.050],
        )
        receiver.timing_decode_samples.extend([0.005])
        receiver.timing_buffer_samples.extend([0.020])

        receiver._log_timing_stats()

        self.assertEqual(len(receiver.timing_decode_samples), 0)
        self.assertEqual(len(receiver.timing_buffer_samples), 0)
        self.assertEqual(len(receiver._timing_receive_samples), 0)
        self.assertEqual(len(receiver._timing_e2e_samples), 0)


class TestOnReceiveProbe(unittest.TestCase):
    def _make_probe_info(self, pts):
        buffer = MagicMock()
        buffer.pts = pts
        info = MagicMock()
        info.get_buffer.return_value = buffer
        return info

    def test_records_first_packet_time(self):
        receiver = _make_receiver(_receive_start_times={})
        info = self._make_probe_info(1000)

        result = receiver._on_receive_probe(MagicMock(), info)

        self.assertEqual(result, _gst_mock.PadProbeReturn.OK)
        self.assertIn(1000, receiver._receive_start_times)

    def test_does_not_overwrite_first_packet(self):
        receiver = _make_receiver(_receive_start_times={1000: 42.0})
        info = self._make_probe_info(1000)

        receiver._on_receive_probe(MagicMock(), info)

        self.assertEqual(receiver._receive_start_times[1000], 42.0)

    def test_ignores_none_buffer(self):
        receiver = _make_receiver(_receive_start_times={})
        info = MagicMock()
        info.get_buffer.return_value = None

        result = receiver._on_receive_probe(MagicMock(), info)

        self.assertEqual(result, _gst_mock.PadProbeReturn.OK)
        self.assertEqual(len(receiver._receive_start_times), 0)

    def test_ignores_clock_time_none(self):
        receiver = _make_receiver(_receive_start_times={})
        info = self._make_probe_info(_gst_mock.CLOCK_TIME_NONE)

        receiver._on_receive_probe(MagicMock(), info)

        self.assertEqual(len(receiver._receive_start_times), 0)


class TestOnDecoderEntryProbe(unittest.TestCase):
    def _make_probe_info(self, pts):
        buffer = MagicMock()
        buffer.pts = pts
        info = MagicMock()
        info.get_buffer.return_value = buffer
        return info

    def test_calculates_receive_duration(self):
        receiver = _make_receiver(
            _receive_start_times={1000: time.monotonic() - 0.05},
            _decode_start_times={},
            _receive_durations={},
        )
        info = self._make_probe_info(1000)

        receiver._on_decoder_entry_probe(MagicMock(), info)

        self.assertIn(1000, receiver._receive_durations)
        self.assertGreater(receiver._receive_durations[1000], 0.04)
        self.assertNotIn(1000, receiver._receive_start_times)

    def test_records_decode_start_time(self):
        receiver = _make_receiver(
            _receive_start_times={},
            _decode_start_times={},
            _receive_durations={},
        )
        info = self._make_probe_info(2000)

        receiver._on_decoder_entry_probe(MagicMock(), info)

        self.assertIn(2000, receiver._decode_start_times)

    def test_no_receive_duration_without_start(self):
        receiver = _make_receiver(
            _receive_start_times={},
            _decode_start_times={},
            _receive_durations={},
        )
        info = self._make_probe_info(3000)

        receiver._on_decoder_entry_probe(MagicMock(), info)

        self.assertNotIn(3000, receiver._receive_durations)


class TestOnSeiExtractProbe(unittest.TestCase):
    def test_extracts_sei_timestamp(self):
        receiver = _make_receiver(_sei_timestamps={})

        from v3xctrl_helper.sei import build_sei_nal

        sei_data = build_sei_nal(123456)

        buffer = MagicMock()
        buffer.pts = 5000
        map_info = MagicMock()
        map_info.data = sei_data
        buffer.map.return_value = (True, map_info)

        info = MagicMock()
        info.get_buffer.return_value = buffer

        result = receiver._on_sei_extract_probe(MagicMock(), info)

        self.assertEqual(result, _gst_mock.PadProbeReturn.OK)
        self.assertIn(5000, receiver._sei_timestamps)
        self.assertEqual(receiver._sei_timestamps[5000], 123456)
        buffer.unmap.assert_called_once_with(map_info)

    def test_ignores_non_sei_data(self):
        receiver = _make_receiver(_sei_timestamps={})

        buffer = MagicMock()
        buffer.pts = 5000
        map_info = MagicMock()
        map_info.data = b"\x00\x00\x00\x01\x65" + b"\x00" * 50
        buffer.map.return_value = (True, map_info)

        info = MagicMock()
        info.get_buffer.return_value = buffer

        receiver._on_sei_extract_probe(MagicMock(), info)

        self.assertNotIn(5000, receiver._sei_timestamps)

    def test_clears_dict_when_exceeding_limit(self):
        sei_timestamps = {i: i for i in range(301)}
        receiver = _make_receiver(_sei_timestamps=sei_timestamps)

        from v3xctrl_helper.sei import build_sei_nal

        sei_data = build_sei_nal(999)

        buffer = MagicMock()
        buffer.pts = 9999
        map_info = MagicMock()
        map_info.data = sei_data
        buffer.map.return_value = (True, map_info)

        info = MagicMock()
        info.get_buffer.return_value = buffer

        receiver._on_sei_extract_probe(MagicMock(), info)

        # Dict was cleared and only the new entry remains
        self.assertEqual(len(receiver._sei_timestamps), 1)
        self.assertEqual(receiver._sei_timestamps[9999], 999)

    def test_handles_map_failure(self):
        receiver = _make_receiver(_sei_timestamps={})

        buffer = MagicMock()
        buffer.pts = 5000
        buffer.map.return_value = (False, None)

        info = MagicMock()
        info.get_buffer.return_value = buffer

        result = receiver._on_sei_extract_probe(MagicMock(), info)

        self.assertEqual(result, _gst_mock.PadProbeReturn.OK)
        self.assertNotIn(5000, receiver._sei_timestamps)


class TestOnFrameDisplayed(unittest.TestCase):
    def test_calculates_e2e_with_valid_offset(self):
        clock_offset = ClockOffset()
        clock_offset.update(viewer_send=1.0, streamer_timestamp=1.005, viewer_receive=1.010)

        receiver = _make_receiver(
            _clock_offset=clock_offset,
            _timing_e2e_samples=deque(maxlen=100),
        )

        # capture_timestamp_us simulates a frame captured 50ms ago
        capture_us = int(time.time() * 1_000_000) - 50_000
        receiver._on_frame_displayed(capture_us)

        self.assertEqual(len(receiver._timing_e2e_samples), 1)
        e2e = receiver._timing_e2e_samples[0]
        # Should be approximately 50ms (0.05s) plus offset adjustment
        self.assertGreater(e2e, 0.03)
        self.assertLess(e2e, 0.15)

    def test_skips_when_capture_timestamp_zero(self):
        clock_offset = ClockOffset()
        clock_offset.update(viewer_send=1.0, streamer_timestamp=1.005, viewer_receive=1.010)

        receiver = _make_receiver(
            _clock_offset=clock_offset,
            _timing_e2e_samples=deque(maxlen=100),
        )

        receiver._on_frame_displayed(0)

        self.assertEqual(len(receiver._timing_e2e_samples), 0)

    def test_skips_when_clock_offset_invalid(self):
        clock_offset = ClockOffset()

        receiver = _make_receiver(
            _clock_offset=clock_offset,
            _timing_e2e_samples=deque(maxlen=100),
        )

        receiver._on_frame_displayed(int(time.time() * 1_000_000) - 50_000)

        self.assertEqual(len(receiver._timing_e2e_samples), 0)

    def test_skips_when_no_clock_offset(self):
        receiver = _make_receiver(
            _clock_offset=None,
            _timing_e2e_samples=deque(maxlen=100),
        )

        receiver._on_frame_displayed(int(time.time() * 1_000_000) - 50_000)

        self.assertEqual(len(receiver._timing_e2e_samples), 0)

    def test_skips_negative_e2e(self):
        clock_offset = ClockOffset()
        clock_offset.update(viewer_send=1.0, streamer_timestamp=1.005, viewer_receive=1.010)

        receiver = _make_receiver(
            _clock_offset=clock_offset,
            _timing_e2e_samples=deque(maxlen=100),
        )

        # Capture timestamp far in the future - would produce negative e2e
        future_us = int(time.time() * 1_000_000) + 10_000_000
        receiver._on_frame_displayed(future_us)

        self.assertEqual(len(receiver._timing_e2e_samples), 0)


class TestSetClockOffset(unittest.TestCase):
    def test_sets_clock_offset(self):
        receiver = _make_receiver()
        clock_offset = ClockOffset()

        receiver.set_clock_offset(clock_offset)

        self.assertIs(receiver._clock_offset, clock_offset)


class TestCleanup(unittest.TestCase):
    def test_cleanup_calls_stop_pipeline(self):
        receiver = _make_receiver()

        receiver._cleanup()

        self.assertIsNone(receiver.pipeline)


if __name__ == "__main__":
    unittest.main(verbosity=2)
