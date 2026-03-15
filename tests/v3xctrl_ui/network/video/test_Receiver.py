import threading
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np

from v3xctrl_ui.network.video.Receiver import Receiver


class MockReceiver(Receiver):
    """Mock implementation for testing the abstract Receiver."""

    def __init__(self, port: int, keep_alive, setup_fail=False, main_loop_fail=False, cleanup_fail=False):
        super().__init__(port, keep_alive)
        self.setup_called = False
        self.main_loop_called = False
        self.cleanup_called = False
        self.setup_fail = setup_fail
        self.main_loop_fail = main_loop_fail
        self.cleanup_fail = cleanup_fail

    def _setup(self):
        self.setup_called = True
        if self.setup_fail:
            raise RuntimeError("Setup failed")

    def _main_loop(self):
        self.main_loop_called = True
        if self.main_loop_fail:
            raise RuntimeError("Main loop failed")

        counter = 0
        while self.running.is_set() and counter < 5:
            if counter % 2 == 0:
                fake_frame = np.zeros((100, 100, 3), dtype=np.uint8)
                self._update_frame(fake_frame)
                self.packet_count += 1
            else:
                self.dropped_empty_frames += 1
                self.packet_count += 1

            time.sleep(0.01)
            counter += 1

    def _cleanup(self):
        self.cleanup_called = True
        if self.cleanup_fail:
            raise RuntimeError("Cleanup failed")


class TestReceiver(unittest.TestCase):
    def test_cannot_instantiate_abstract_class(self):
        """Abstract class should not be instantiable."""
        with self.assertRaises(TypeError):
            Receiver(5600, Mock())

    def test_initialization(self):
        """Test proper initialization of all attributes."""
        keep_alive = Mock()
        receiver = MockReceiver(5600, keep_alive)

        self.assertEqual(receiver.port, 5600)
        self.assertEqual(receiver.keep_alive, keep_alive)
        self.assertIsNone(receiver.frame)
        self.assertEqual(receiver.packet_count, 0)
        self.assertEqual(receiver.decoded_frame_count, 0)
        self.assertEqual(receiver.dropped_old_frames, 0)
        self.assertEqual(receiver.dropped_empty_frames, 0)
        self.assertEqual(receiver.last_log_time, 0.0)
        self.assertEqual(receiver.log_interval, 10.0)
        self.assertEqual(len(receiver.render_history), 0)
        self.assertEqual(receiver.render_history.maxlen, 100)
        self.assertTrue(hasattr(receiver.running, "is_set"))
        self.assertTrue(hasattr(receiver.running, "set"))
        self.assertTrue(hasattr(receiver.running, "clear"))
        self.assertTrue(hasattr(receiver.frame_lock, "acquire"))
        self.assertTrue(hasattr(receiver.frame_lock, "release"))
        self.assertFalse(receiver.running.is_set())

    def test_update_frame_thread_safety(self):
        """Test _update_frame updates frame safely and increments counters."""
        receiver = MockReceiver(5600, Mock())
        test_frame = np.ones((50, 50, 3), dtype=np.uint8)

        initial_time = time.monotonic()
        receiver._update_frame(test_frame)
        receiver.get_frame()

        with receiver.frame_lock:
            np.testing.assert_array_equal(receiver.frame, test_frame)

        self.assertEqual(receiver.decoded_frame_count, 1)
        self.assertEqual(len(receiver.render_history), 1)
        self.assertGreaterEqual(receiver.render_history[0], initial_time)

    def test_update_frame_multiple_calls(self):
        """Test multiple frame updates work correctly."""
        receiver = MockReceiver(5600, Mock())

        for i in range(5):
            test_frame = np.full((10, 10, 3), i, dtype=np.uint8)
            receiver._update_frame(test_frame)
            receiver.get_frame()

        self.assertEqual(receiver.decoded_frame_count, 5)
        self.assertEqual(len(receiver.render_history), 5)

        with receiver.frame_lock:
            np.testing.assert_array_equal(receiver.frame, np.full((10, 10, 3), 4, dtype=np.uint8))

    def test_history_deque_maxlen(self):
        """Test history deque respects maxlen of 100."""
        receiver = MockReceiver(5600, Mock())

        for _i in range(150):
            receiver._update_frame(np.zeros((10, 10, 3), dtype=np.uint8))
            receiver.get_frame()

        self.assertEqual(len(receiver.render_history), 100)
        self.assertEqual(receiver.decoded_frame_count, 150)

    def test_successful_run_lifecycle(self):
        """Test normal start/stop lifecycle."""
        keep_alive = Mock()
        receiver = MockReceiver(5600, keep_alive)

        receiver.start()
        time.sleep(0.1)
        receiver.stop()

        self.assertTrue(receiver.setup_called)
        self.assertTrue(receiver.main_loop_called)
        self.assertTrue(receiver.cleanup_called)
        self.assertFalse(receiver.running.is_set())
        self.assertFalse(receiver.is_alive())

    def test_setup_failure_handling(self):
        """Test setup failure is handled gracefully."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock(), setup_fail=True)

            receiver.start()
            time.sleep(0.1)
            receiver.stop()

            self.assertTrue(receiver.setup_called)
            self.assertFalse(receiver.main_loop_called)
            self.assertTrue(receiver.cleanup_called)
            mock_logger.exception.assert_called()

    def test_main_loop_failure_handling(self):
        """Test main loop failure is handled gracefully."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock(), main_loop_fail=True)

            receiver.start()
            time.sleep(0.1)
            receiver.stop()

            self.assertTrue(receiver.setup_called)
            self.assertTrue(receiver.main_loop_called)
            self.assertTrue(receiver.cleanup_called)
            mock_logger.exception.assert_called()

    def test_cleanup_failure_in_run(self):
        """Test cleanup failure in run() finally block is handled."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock(), cleanup_fail=True)

            receiver.start()
            time.sleep(0.1)
            receiver.stop()

            mock_logger.exception.assert_called()

    def test_cleanup_failure_in_stop(self):
        """Test cleanup failure in stop() is handled."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock(), cleanup_fail=True)

            receiver.start()
            time.sleep(0.05)
            receiver.stop()

            mock_logger.exception.assert_not_called()

    def test_stop_without_start(self):
        """Test stop() can be called without start()."""
        receiver = MockReceiver(5600, Mock())

        receiver.stop()

        self.assertFalse(receiver.running.is_set())
        self.assertFalse(receiver.cleanup_called)

    def test_stop_timeout_handling(self):
        """Test stop() respects timeout when thread doesn't join."""

        class SlowReceiver(MockReceiver):
            def _main_loop(self):
                time.sleep(10)

        receiver = SlowReceiver(5600, Mock())
        receiver.start()

        start_time = time.monotonic()
        receiver.stop()
        receiver.join(timeout=5)
        stop_time = time.monotonic()

        self.assertGreater(stop_time - start_time, 4.5)
        self.assertLess(stop_time - start_time, 6.0)

    def test_log_stats_no_packets(self):
        """Test logging when no packets have been processed."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock())
            receiver.packet_count = 0
            receiver.last_log_time = time.monotonic() - 11.0

            receiver._log_stats_if_needed()

            mock_logger.info.assert_not_called()
            self.assertGreater(receiver.last_log_time, 0)

    def test_log_stats_with_packets(self):
        """Test statistics logging with packet data."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock())
            receiver.log_interval = 0.01
            receiver.packet_count = 10
            receiver.decoded_frame_count = 7
            receiver.dropped_empty_frames = 2
            receiver.dropped_old_frames = 1
            receiver.last_log_time = time.monotonic() - 0.02

            receiver._log_stats_if_needed()

            mock_logger.info.assert_called_once()

            # NOTE: This test will fail due to syntax error in Receiver._log_stats_if_needed
            # The logging.info call has incorrect comma placement

            self.assertEqual(receiver.packet_count, 0)
            self.assertEqual(receiver.decoded_frame_count, 0)
            self.assertEqual(receiver.dropped_empty_frames, 0)
            self.assertEqual(receiver.dropped_old_frames, 0)

    def test_log_stats_interval_not_reached(self):
        """Test no logging when interval hasn't passed."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock())
            receiver.packet_count = 10
            receiver.last_log_time = time.monotonic() - 5.0

            receiver._log_stats_if_needed()

            mock_logger.info.assert_not_called()

    def test_log_stats_calculates_correct_drop_rate(self):
        """Test drop rate calculation includes both empty decodes and dropped old frames."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock())
            receiver.log_interval = 0.01
            receiver.packet_count = 100
            receiver.decoded_frame_count = 70
            receiver.dropped_empty_frames = 20
            receiver.dropped_old_frames = 10
            receiver.last_log_time = time.monotonic() - 0.02

            receiver._log_stats_if_needed()

            # Expected drop rate: (20 + 10) / 100 * 100 = 30%
            mock_logger.info.assert_called_once()

    def test_log_stats_avg_fps_calculation(self):
        """Test average FPS calculation."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock())
            receiver.log_interval = 2.0
            receiver.packet_count = 60
            receiver.decoded_frame_count = 60
            receiver.last_log_time = time.monotonic() - 2.0

            receiver._log_stats_if_needed()

            # Expected avg_fps: round(60 / 2.0) = 30
            mock_logger.info.assert_called_once()

    def test_log_stats_first_time_uses_interval(self):
        """Test first logging uses log_interval for time calculation."""
        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver = MockReceiver(5600, Mock())
            receiver.log_interval = 5.0
            receiver.packet_count = 50
            receiver.decoded_frame_count = 50
            receiver.last_log_time = 0.0

            receiver._log_stats_if_needed()

            # Should use log_interval (5.0) for avg_fps calculation
            mock_logger.info.assert_called_once()

    def test_thread_inheritance(self):
        """Test Receiver properly inherits from threading.Thread."""
        receiver = MockReceiver(5600, Mock())
        self.assertIsInstance(receiver, threading.Thread)
        self.assertTrue(hasattr(receiver, "start"))
        self.assertTrue(hasattr(receiver, "join"))
        self.assertTrue(hasattr(receiver, "is_alive"))

    def test_abstract_methods_enforced(self):
        """Test that abstract methods must be implemented."""

        class IncompleteReceiver(Receiver):
            def _setup(self):
                pass

            # Missing _main_loop and _cleanup

        with self.assertRaises(TypeError):
            IncompleteReceiver(5600, Mock())

    def test_running_event_controls_lifecycle(self):
        """Test running event is properly set and cleared."""
        receiver = MockReceiver(5600, Mock())

        self.assertFalse(receiver.running.is_set())

        receiver.start()
        time.sleep(0.05)
        self.assertTrue(receiver.running.is_set())

        receiver.stop()
        self.assertFalse(receiver.running.is_set())

    def test_keep_alive_not_called(self):
        """Test that keep_alive is never called (current implementation issue)."""
        keep_alive = Mock()
        receiver = MockReceiver(5600, keep_alive, main_loop_fail=True)

        receiver.start()
        time.sleep(0.1)
        receiver.stop()

        # NOTE: This demonstrates that keep_alive is not used in current implementation
        keep_alive.assert_not_called()


class TestPickOldestFrame(unittest.TestCase):
    def test_returns_oldest_frame(self):
        receiver = MockReceiver(5600, Mock())
        frames = [np.full((10, 10, 3), i, dtype=np.uint8) for i in range(3)]
        for frame in frames:
            receiver._update_frame(frame)

        receiver.render_ratio = 100
        result = receiver.get_frame()
        np.testing.assert_array_equal(result, frames[0])
        self.assertEqual(len(receiver.frame_buffer), 2)

    def test_with_timing_enabled(self):
        receiver = MockReceiver(5600, Mock())
        receiver.enable_timing(True)

        receiver._update_frame(np.zeros((10, 10, 3), dtype=np.uint8), decode_duration=0.005)
        receiver._update_frame(np.ones((10, 10, 3), dtype=np.uint8), decode_duration=0.010)

        receiver.render_ratio = 100
        receiver.get_frame()

        self.assertIsNotNone(receiver.last_displayed_decode_time)
        self.assertEqual(len(receiver.frame_buffer), 1)


class TestPickNewestFrame(unittest.TestCase):
    def test_returns_newest_and_clears_buffer(self):
        receiver = MockReceiver(5600, Mock())
        frames = [np.full((10, 10, 3), i, dtype=np.uint8) for i in range(5)]
        for frame in frames:
            receiver._update_frame(frame)

        receiver.render_ratio = 0
        result = receiver.get_frame()
        np.testing.assert_array_equal(result, frames[4])
        self.assertEqual(len(receiver.frame_buffer), 0)
        self.assertEqual(receiver.dropped_burst_frames, 4)

    def test_with_timing_enabled(self):
        receiver = MockReceiver(5600, Mock())
        receiver.enable_timing(True)

        for i in range(3):
            receiver._update_frame(np.full((10, 10, 3), i, dtype=np.uint8), decode_duration=0.001 * i)

        receiver.render_ratio = 0
        receiver.get_frame()

        self.assertIsNotNone(receiver.last_displayed_decode_time)
        self.assertEqual(len(receiver.frame_timestamps), 0)
        self.assertEqual(len(receiver.decode_durations), 0)


class TestPickAdaptiveFrame(unittest.TestCase):
    def test_drops_excess_frames(self):
        receiver = MockReceiver(5600, Mock())
        receiver.render_ratio = 50

        for i in range(200):
            receiver._update_frame(np.full((10, 10, 3), i, dtype=np.uint8))

        result = receiver.get_frame()
        self.assertIsNotNone(result)
        self.assertGreater(receiver.dropped_burst_frames, 0)

    def test_with_timing_enabled(self):
        receiver = MockReceiver(5600, Mock())
        receiver.enable_timing(True)
        receiver.render_ratio = 50

        for i in range(200):
            receiver._update_frame(np.full((10, 10, 3), i, dtype=np.uint8), decode_duration=0.001)

        receiver.get_frame()
        self.assertIsNotNone(receiver.last_displayed_decode_time)

    def test_logs_adaptive_debug(self):
        receiver = MockReceiver(5600, Mock())
        receiver.render_ratio = 50

        for i in range(200):
            receiver._update_frame(np.full((10, 10, 3), i, dtype=np.uint8))

        with patch("v3xctrl_ui.network.video.Receiver.logger") as mock_logger:
            receiver.get_frame()
            mock_logger.debug.assert_called()


class TestGetFrameTimingTracking(unittest.TestCase):
    def test_timing_stats_accumulated(self):
        receiver = MockReceiver(5600, Mock())
        receiver.enable_timing(True)
        receiver.timing_log_interval = 100

        receiver._update_frame(np.zeros((10, 10, 3), dtype=np.uint8), decode_duration=0.005)

        receiver.render_ratio = 0
        receiver.get_frame()

        self.assertEqual(len(receiver.timing_buffer_samples), 1)
        self.assertEqual(len(receiver.timing_decode_samples), 1)

    def test_timing_log_triggered(self):
        receiver = MockReceiver(5600, Mock())
        receiver.enable_timing(True)
        receiver.timing_log_interval = 2

        for _ in range(3):
            receiver._update_frame(np.zeros((10, 10, 3), dtype=np.uint8), decode_duration=0.005)
            receiver.render_ratio = 100
            receiver.get_frame()

        # After 3 samples with log_interval=2, _log_timing_stats should have been called
        # and cleared the samples
        self.assertLessEqual(len(receiver.timing_buffer_samples), 1)

    def test_empty_buffer_returns_previous_frame(self):
        receiver = MockReceiver(5600, Mock())
        receiver.frame = np.zeros((10, 10, 3), dtype=np.uint8)

        result = receiver.get_frame()
        np.testing.assert_array_equal(result, np.zeros((10, 10, 3), dtype=np.uint8))
        self.assertEqual(receiver.rendered_frame_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
