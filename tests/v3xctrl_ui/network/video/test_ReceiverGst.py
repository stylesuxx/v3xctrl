import time
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

import numpy as np


@patch("v3xctrl_ui.network.video.ReceiverGst.Gst")
@patch("v3xctrl_ui.network.video.ReceiverGst.GstApp")
@patch("v3xctrl_ui.network.video.ReceiverGst.GLib")
@patch("v3xctrl_ui.network.video.ReceiverGst.NTPClock")
class TestShouldDropByAge(unittest.TestCase):
    def _create_receiver(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        mock_gst.CLOCK_TIME_NONE = -1
        mock_gst.SECOND = 1_000_000_000

        from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst

        receiver = ReceiverGst.__new__(ReceiverGst)
        receiver.max_age_seconds = 0.5
        receiver.latest_pts = None
        mock_gst_ref = mock_gst
        receiver._gst_CLOCK_TIME_NONE = mock_gst_ref.CLOCK_TIME_NONE
        receiver._gst_SECOND = mock_gst_ref.SECOND
        return receiver, mock_gst

    def test_clock_time_none_is_not_dropped(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        self.assertFalse(receiver._should_drop_by_age(mock_gst.CLOCK_TIME_NONE))

    def test_first_frame_is_not_dropped(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, _ = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        self.assertFalse(receiver._should_drop_by_age(1_000_000_000))
        self.assertEqual(receiver.latest_pts, 1_000_000_000)

    def test_newer_frame_updates_latest_pts(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, _ = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.latest_pts = 1_000_000_000

        self.assertFalse(receiver._should_drop_by_age(2_000_000_000))
        self.assertEqual(receiver.latest_pts, 2_000_000_000)

    def test_slightly_older_frame_is_not_dropped(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, _ = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.latest_pts = 2_000_000_000

        # 100ms old - under 500ms threshold
        self.assertFalse(receiver._should_drop_by_age(1_900_000_000))

    def test_old_frame_is_dropped(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, _ = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.latest_pts = 2_000_000_000

        # 600ms old - over 500ms threshold
        self.assertTrue(receiver._should_drop_by_age(1_400_000_000))

    def test_frame_exactly_at_threshold_is_dropped(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, _ = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.latest_pts = 2_000_000_000

        # Exactly 500ms old
        self.assertTrue(receiver._should_drop_by_age(1_500_000_000))


@patch("v3xctrl_ui.network.video.ReceiverGst.Gst")
@patch("v3xctrl_ui.network.video.ReceiverGst.GstApp")
@patch("v3xctrl_ui.network.video.ReceiverGst.GLib")
@patch("v3xctrl_ui.network.video.ReceiverGst.NTPClock")
class TestCheckTimeout(unittest.TestCase):
    def _create_receiver(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst

        receiver = ReceiverGst.__new__(ReceiverGst)
        receiver.timeout_seconds = 5.0
        receiver.frame_lock = MagicMock()
        receiver.frame = None
        receiver.frame_buffer = deque()
        receiver.last_frame_time = 0.0
        return receiver

    def test_returns_true_when_no_frames_received(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        self.assertTrue(receiver._check_timeout())

    def test_returns_true_when_not_timed_out(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.last_frame_time = time.monotonic()

        self.assertTrue(receiver._check_timeout())
        self.assertIsNone(receiver.frame)

    def test_clears_frame_on_timeout(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.last_frame_time = time.monotonic() - 10.0
        receiver.frame = np.zeros((100, 100, 3), dtype=np.uint8)
        receiver.frame_buffer = deque([np.zeros((100, 100, 3), dtype=np.uint8)])

        receiver._check_timeout()

        self.assertIsNone(receiver.frame)
        self.assertEqual(len(receiver.frame_buffer), 0)

    def test_does_not_clear_when_already_none(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.last_frame_time = time.monotonic() - 10.0
        receiver.frame = None
        receiver.frame_buffer = deque()

        # Should not enter the clearing block (frame is already None and buffer empty)
        receiver._check_timeout()

        self.assertIsNone(receiver.frame)


@patch("v3xctrl_ui.network.video.ReceiverGst.Gst")
@patch("v3xctrl_ui.network.video.ReceiverGst.GstApp")
@patch("v3xctrl_ui.network.video.ReceiverGst.GLib")
@patch("v3xctrl_ui.network.video.ReceiverGst.NTPClock")
class TestStopPipeline(unittest.TestCase):
    def _create_receiver(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst

        receiver = ReceiverGst.__new__(ReceiverGst)
        receiver.pipeline = None
        receiver.appsink = None
        receiver.loop = None
        receiver._receive_start_times = None
        receiver._decode_start_times = None
        receiver._receive_durations = None
        receiver._timing_receive_samples = None
        receiver._sei_timestamps = None
        receiver._timing_e2e_samples = None
        return receiver

    def test_cleanup_with_no_pipeline(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        # Should not raise
        receiver._stop_pipeline()

        self.assertIsNone(receiver.pipeline)
        self.assertIsNone(receiver.appsink)
        self.assertIsNone(receiver.loop)

    def test_cleanup_stops_pipeline(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        mock_pipeline = MagicMock()
        receiver.pipeline = mock_pipeline

        receiver._stop_pipeline()

        mock_pipeline.set_state.assert_called_once_with(mock_gst.State.NULL)
        self.assertIsNone(receiver.pipeline)
        self.assertIsNone(receiver.appsink)

    def test_cleanup_quits_running_loop(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        receiver.loop = mock_loop

        receiver._stop_pipeline()

        mock_loop.quit.assert_called_once()
        self.assertIsNone(receiver.loop)

    def test_cleanup_clears_timing_dicts(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver._receive_start_times = {1: 0.5, 2: 0.6}
        receiver._decode_start_times = {1: 0.7}
        receiver._receive_durations = {1: 0.1}
        receiver._timing_receive_samples = [0.1, 0.2]
        receiver._sei_timestamps = {1: (100, 50)}
        receiver._timing_e2e_samples = [0.05]

        receiver._stop_pipeline()

        self.assertEqual(len(receiver._receive_start_times), 0)
        self.assertEqual(len(receiver._decode_start_times), 0)
        self.assertEqual(len(receiver._receive_durations), 0)
        self.assertEqual(len(receiver._timing_receive_samples), 0)
        self.assertEqual(len(receiver._sei_timestamps), 0)
        self.assertEqual(len(receiver._timing_e2e_samples), 0)


@patch("v3xctrl_ui.network.video.ReceiverGst.Gst")
@patch("v3xctrl_ui.network.video.ReceiverGst.GstApp")
@patch("v3xctrl_ui.network.video.ReceiverGst.GLib")
@patch("v3xctrl_ui.network.video.ReceiverGst.NTPClock")
class TestLogTimingStats(unittest.TestCase):
    def _create_receiver(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst

        receiver = ReceiverGst.__new__(ReceiverGst)
        receiver.timing_decode_samples = deque(maxlen=100)
        receiver.timing_buffer_samples = deque(maxlen=100)
        receiver._timing_receive_samples = []
        receiver._timing_e2e_samples = []
        return receiver

    def test_no_output_when_empty(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        with patch("v3xctrl_ui.network.video.ReceiverGst.logger") as mock_logger:
            receiver._log_timing_stats()

        mock_logger.debug.assert_not_called()

    def test_logs_timing_without_e2e(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.timing_decode_samples.extend([0.005, 0.010])
        receiver.timing_buffer_samples.extend([0.020, 0.030])
        receiver._timing_receive_samples = [0.002, 0.003]

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

    def test_logs_timing_with_e2e(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.timing_decode_samples.extend([0.005])
        receiver.timing_buffer_samples.extend([0.020])
        receiver._timing_receive_samples = [0.002]
        receiver._timing_e2e_samples = [0.050, 0.060]

        with patch("v3xctrl_ui.network.video.ReceiverGst.logger") as mock_logger:
            receiver._log_timing_stats()

        log_msg = mock_logger.debug.call_args[0][0]
        self.assertIn("e2e", log_msg)

    def test_clears_samples_after_logging(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver.timing_decode_samples.extend([0.005])
        receiver.timing_buffer_samples.extend([0.020])
        receiver._timing_receive_samples = [0.002]
        receiver._timing_e2e_samples = [0.050]

        receiver._log_timing_stats()

        self.assertEqual(len(receiver.timing_decode_samples), 0)
        self.assertEqual(len(receiver.timing_buffer_samples), 0)
        self.assertEqual(len(receiver._timing_receive_samples), 0)
        self.assertEqual(len(receiver._timing_e2e_samples), 0)


@patch("v3xctrl_ui.network.video.ReceiverGst.Gst")
@patch("v3xctrl_ui.network.video.ReceiverGst.GstApp")
@patch("v3xctrl_ui.network.video.ReceiverGst.GLib")
@patch("v3xctrl_ui.network.video.ReceiverGst.NTPClock")
class TestOnReceiveProbe(unittest.TestCase):
    def _create_receiver(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        mock_gst.CLOCK_TIME_NONE = -1
        mock_gst.PadProbeReturn.OK = 0

        from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst

        receiver = ReceiverGst.__new__(ReceiverGst)
        receiver._receive_start_times = {}
        return receiver, mock_gst

    def _make_probe_info(self, pts, mock_gst):
        buffer = MagicMock()
        buffer.pts = pts
        info = MagicMock()
        info.get_buffer.return_value = buffer
        return info

    def test_records_first_packet_time(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        info = self._make_probe_info(1000, mock_gst)

        result = receiver._on_receive_probe(MagicMock(), info)

        self.assertEqual(result, mock_gst.PadProbeReturn.OK)
        self.assertIn(1000, receiver._receive_start_times)

    def test_does_not_overwrite_first_packet(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver._receive_start_times[1000] = 42.0
        info = self._make_probe_info(1000, mock_gst)

        receiver._on_receive_probe(MagicMock(), info)

        self.assertEqual(receiver._receive_start_times[1000], 42.0)

    def test_ignores_none_buffer(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        info = MagicMock()
        info.get_buffer.return_value = None

        result = receiver._on_receive_probe(MagicMock(), info)

        self.assertEqual(result, mock_gst.PadProbeReturn.OK)
        self.assertEqual(len(receiver._receive_start_times), 0)

    def test_ignores_clock_time_none(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        info = self._make_probe_info(mock_gst.CLOCK_TIME_NONE, mock_gst)

        receiver._on_receive_probe(MagicMock(), info)

        self.assertEqual(len(receiver._receive_start_times), 0)


@patch("v3xctrl_ui.network.video.ReceiverGst.Gst")
@patch("v3xctrl_ui.network.video.ReceiverGst.GstApp")
@patch("v3xctrl_ui.network.video.ReceiverGst.GLib")
@patch("v3xctrl_ui.network.video.ReceiverGst.NTPClock")
class TestOnDecoderEntryProbe(unittest.TestCase):
    def _create_receiver(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        mock_gst.CLOCK_TIME_NONE = -1
        mock_gst.PadProbeReturn.OK = 0

        from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst

        receiver = ReceiverGst.__new__(ReceiverGst)
        receiver._receive_start_times = {}
        receiver._decode_start_times = {}
        receiver._receive_durations = {}
        return receiver, mock_gst

    def _make_probe_info(self, pts, mock_gst):
        buffer = MagicMock()
        buffer.pts = pts
        info = MagicMock()
        info.get_buffer.return_value = buffer
        return info

    def test_calculates_receive_duration(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        receiver._receive_start_times[1000] = time.monotonic() - 0.05
        info = self._make_probe_info(1000, mock_gst)

        receiver._on_decoder_entry_probe(MagicMock(), info)

        self.assertIn(1000, receiver._receive_durations)
        self.assertGreater(receiver._receive_durations[1000], 0.04)
        self.assertNotIn(1000, receiver._receive_start_times)

    def test_records_decode_start_time(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        info = self._make_probe_info(2000, mock_gst)

        receiver._on_decoder_entry_probe(MagicMock(), info)

        self.assertIn(2000, receiver._decode_start_times)

    def test_no_receive_duration_without_start(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        info = self._make_probe_info(3000, mock_gst)

        receiver._on_decoder_entry_probe(MagicMock(), info)

        self.assertNotIn(3000, receiver._receive_durations)


@patch("v3xctrl_ui.network.video.ReceiverGst.Gst")
@patch("v3xctrl_ui.network.video.ReceiverGst.GstApp")
@patch("v3xctrl_ui.network.video.ReceiverGst.GLib")
@patch("v3xctrl_ui.network.video.ReceiverGst.NTPClock")
class TestOnSeiExtractProbe(unittest.TestCase):
    def _create_receiver(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        mock_gst.CLOCK_TIME_NONE = -1
        mock_gst.PadProbeReturn.OK = 0
        mock_gst.MapFlags.READ = 1

        from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst

        receiver = ReceiverGst.__new__(ReceiverGst)
        receiver._sei_timestamps = {}
        return receiver, mock_gst

    def test_extracts_sei_timestamp(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        from v3xctrl_helper.sei import build_sei_nal

        sei_data = build_sei_nal(123456, -42)

        buffer = MagicMock()
        buffer.pts = 5000
        map_info = MagicMock()
        map_info.data = sei_data
        buffer.map.return_value = (True, map_info)

        info = MagicMock()
        info.get_buffer.return_value = buffer

        result = receiver._on_sei_extract_probe(MagicMock(), info)

        self.assertEqual(result, mock_gst.PadProbeReturn.OK)
        self.assertIn(5000, receiver._sei_timestamps)
        self.assertEqual(receiver._sei_timestamps[5000], (123456, -42))
        buffer.unmap.assert_called_once_with(map_info)

    def test_ignores_non_sei_data(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        buffer = MagicMock()
        buffer.pts = 5000
        map_info = MagicMock()
        map_info.data = b"\x00\x00\x00\x01\x65" + b"\x00" * 50
        buffer.map.return_value = (True, map_info)

        info = MagicMock()
        info.get_buffer.return_value = buffer

        receiver._on_sei_extract_probe(MagicMock(), info)

        self.assertNotIn(5000, receiver._sei_timestamps)

    def test_clears_dict_when_exceeding_limit(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        # Fill past the 300 limit
        for i in range(301):
            receiver._sei_timestamps[i] = (i, 0)

        from v3xctrl_helper.sei import build_sei_nal

        sei_data = build_sei_nal(999, 111)

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
        self.assertEqual(receiver._sei_timestamps[9999], (999, 111))

    def test_handles_map_failure(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver, mock_gst = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        buffer = MagicMock()
        buffer.pts = 5000
        buffer.map.return_value = (False, None)

        info = MagicMock()
        info.get_buffer.return_value = buffer

        result = receiver._on_sei_extract_probe(MagicMock(), info)

        self.assertEqual(result, mock_gst.PadProbeReturn.OK)
        self.assertNotIn(5000, receiver._sei_timestamps)


@patch("v3xctrl_ui.network.video.ReceiverGst.Gst")
@patch("v3xctrl_ui.network.video.ReceiverGst.GstApp")
@patch("v3xctrl_ui.network.video.ReceiverGst.GLib")
@patch("v3xctrl_ui.network.video.ReceiverGst.NTPClock")
class TestCleanup(unittest.TestCase):
    def _create_receiver(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        from v3xctrl_ui.network.video.ReceiverGst import ReceiverGst

        receiver = ReceiverGst.__new__(ReceiverGst)
        receiver.pipeline = None
        receiver.appsink = None
        receiver.loop = None
        receiver._receive_start_times = None
        receiver._decode_start_times = None
        receiver._receive_durations = None
        receiver._timing_receive_samples = None
        receiver._sei_timestamps = None
        receiver._timing_e2e_samples = None
        receiver._ntp_clock = None
        return receiver

    def test_cleanup_stops_ntp_clock(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)
        mock_clock = MagicMock()
        receiver._ntp_clock = mock_clock

        receiver._cleanup()

        mock_clock.stop.assert_called_once()
        self.assertIsNone(receiver._ntp_clock)

    def test_cleanup_without_ntp_clock(self, mock_ntp, mock_glib, mock_gstapp, mock_gst):
        receiver = self._create_receiver(mock_ntp, mock_glib, mock_gstapp, mock_gst)

        # Should not raise
        receiver._cleanup()

        self.assertIsNone(receiver._ntp_clock)


if __name__ == "__main__":
    unittest.main(verbosity=2)
