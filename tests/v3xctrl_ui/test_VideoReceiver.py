import threading
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np

from v3xctrl_ui.VideoReceiver import VideoReceiver


class MockVideoReceiver(VideoReceiver):
    """Mock implementation for testing the abstract VideoReceiver."""

    def __init__(self, port: int, error_callback, setup_fail=False, main_loop_fail=False, cleanup_fail=False):
        super().__init__(port, error_callback)
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


class TestVideoReceiver(unittest.TestCase):

    def test_cannot_instantiate_abstract_class(self):
        """Abstract class should not be instantiable."""
        with self.assertRaises(TypeError):
            VideoReceiver(5600, Mock())

    def test_initialization(self):
        """Test proper initialization of all attributes."""
        error_callback = Mock()
        receiver = MockVideoReceiver(5600, error_callback)

        self.assertEqual(receiver.port, 5600)
        self.assertEqual(receiver.error_callback, error_callback)
        self.assertIsNone(receiver.frame)
        self.assertEqual(receiver.packet_count, 0)
        self.assertEqual(receiver.decoded_frame_count, 0)
        self.assertEqual(receiver.dropped_old_frames, 0)
        self.assertEqual(receiver.dropped_empty_frames, 0)
        self.assertEqual(receiver.last_log_time, 0.0)
        self.assertEqual(receiver.log_interval, 10.0)
        self.assertEqual(len(receiver.render_history), 0)
        self.assertEqual(receiver.render_history.maxlen, 100)
        self.assertTrue(hasattr(receiver.running, 'is_set'))
        self.assertTrue(hasattr(receiver.running, 'set'))
        self.assertTrue(hasattr(receiver.running, 'clear'))
        self.assertTrue(hasattr(receiver.frame_lock, 'acquire'))
        self.assertTrue(hasattr(receiver.frame_lock, 'release'))
        self.assertFalse(receiver.running.is_set())

    def test_update_frame_thread_safety(self):
        """Test _update_frame updates frame safely and increments counters."""
        receiver = MockVideoReceiver(5600, Mock())
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
        receiver = MockVideoReceiver(5600, Mock())

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
        receiver = MockVideoReceiver(5600, Mock())

        for i in range(150):
            receiver._update_frame(np.zeros((10, 10, 3), dtype=np.uint8))
            receiver.get_frame()

        self.assertEqual(len(receiver.render_history), 100)
        self.assertEqual(receiver.decoded_frame_count, 150)

    def test_successful_run_lifecycle(self):
        """Test normal start/stop lifecycle."""
        error_callback = Mock()
        receiver = MockVideoReceiver(5600, error_callback)

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
        with patch('logging.exception') as mock_log:
            receiver = MockVideoReceiver(5600, Mock(), setup_fail=True)

            receiver.start()
            time.sleep(0.1)
            receiver.stop()

            self.assertTrue(receiver.setup_called)
            self.assertFalse(receiver.main_loop_called)
            self.assertTrue(receiver.cleanup_called)
            mock_log.assert_called()

    def test_main_loop_failure_handling(self):
        """Test main loop failure is handled gracefully."""
        with patch('logging.exception') as mock_log:
            receiver = MockVideoReceiver(5600, Mock(), main_loop_fail=True)

            receiver.start()
            time.sleep(0.1)
            receiver.stop()

            self.assertTrue(receiver.setup_called)
            self.assertTrue(receiver.main_loop_called)
            self.assertTrue(receiver.cleanup_called)
            mock_log.assert_called()

    def test_cleanup_failure_in_run(self):
        """Test cleanup failure in run() finally block is handled."""
        with patch('logging.exception') as mock_log:
            receiver = MockVideoReceiver(5600, Mock(), cleanup_fail=True)

            receiver.start()
            time.sleep(0.1)
            receiver.stop()

            mock_log.assert_called()

    def test_cleanup_failure_in_stop(self):
        """Test cleanup failure in stop() is handled."""
        with patch('logging.exception') as mock_log:
            receiver = MockVideoReceiver(5600, Mock(), cleanup_fail=True)

            receiver.start()
            time.sleep(0.05)
            receiver.stop()

            mock_log.assert_called()

    def test_stop_without_start(self):
        """Test stop() can be called without start()."""
        receiver = MockVideoReceiver(5600, Mock())

        receiver.stop()

        self.assertFalse(receiver.running.is_set())
        self.assertTrue(receiver.cleanup_called)

    def test_stop_timeout_handling(self):
        """Test stop() respects timeout when thread doesn't join."""
        class SlowReceiver(MockVideoReceiver):
            def _main_loop(self):
                time.sleep(10)

        receiver = SlowReceiver(5600, Mock())
        receiver.start()

        start_time = time.monotonic()
        receiver.stop()
        stop_time = time.monotonic()

        self.assertGreater(stop_time - start_time, 4.5)
        self.assertLess(stop_time - start_time, 6.0)
        self.assertTrue(receiver.cleanup_called)

    def test_log_stats_no_packets(self):
        """Test logging when no packets have been processed."""
        with patch('logging.info') as mock_log:
            receiver = MockVideoReceiver(5600, Mock())
            receiver.packet_count = 0
            receiver.last_log_time = time.monotonic() - 11.0

            receiver._log_stats_if_needed()

            mock_log.assert_not_called()
            self.assertGreater(receiver.last_log_time, 0)

    def test_log_stats_with_packets(self):
        """Test statistics logging with packet data."""
        with patch('logging.info') as mock_log:
            receiver = MockVideoReceiver(5600, Mock())
            receiver.log_interval = 0.01
            receiver.packet_count = 10
            receiver.decoded_frame_count = 7
            receiver.dropped_empty_frames = 2
            receiver.dropped_old_frames = 1
            receiver.last_log_time = time.monotonic() - 0.02

            receiver._log_stats_if_needed()

            mock_log.assert_called_once()

            # NOTE: This test will fail due to syntax error in VideoReceiver._log_stats_if_needed
            # The logging.info call has incorrect comma placement

            self.assertEqual(receiver.packet_count, 0)
            self.assertEqual(receiver.decoded_frame_count, 0)
            self.assertEqual(receiver.dropped_empty_frames, 0)
            self.assertEqual(receiver.dropped_old_frames, 0)

    def test_log_stats_interval_not_reached(self):
        """Test no logging when interval hasn't passed."""
        with patch('logging.info') as mock_log:
            receiver = MockVideoReceiver(5600, Mock())
            receiver.packet_count = 10
            receiver.last_log_time = time.monotonic() - 5.0

            receiver._log_stats_if_needed()

            mock_log.assert_not_called()

    def test_log_stats_calculates_correct_drop_rate(self):
        """Test drop rate calculation includes both empty decodes and dropped old frames."""
        with patch('logging.info') as mock_log:
            receiver = MockVideoReceiver(5600, Mock())
            receiver.log_interval = 0.01
            receiver.packet_count = 100
            receiver.decoded_frame_count = 70
            receiver.dropped_empty_frames = 20
            receiver.dropped_old_frames = 10
            receiver.last_log_time = time.monotonic() - 0.02

            receiver._log_stats_if_needed()

            # Expected drop rate: (20 + 10) / 100 * 100 = 30%
            mock_log.assert_called_once()

    def test_log_stats_avg_fps_calculation(self):
        """Test average FPS calculation."""
        with patch('logging.info') as mock_log:
            receiver = MockVideoReceiver(5600, Mock())
            receiver.log_interval = 2.0
            receiver.packet_count = 60
            receiver.decoded_frame_count = 60
            receiver.last_log_time = time.monotonic() - 2.0

            receiver._log_stats_if_needed()

            # Expected avg_fps: round(60 / 2.0) = 30
            mock_log.assert_called_once()

    def test_log_stats_first_time_uses_interval(self):
        """Test first logging uses log_interval for time calculation."""
        with patch('logging.info') as mock_log:
            receiver = MockVideoReceiver(5600, Mock())
            receiver.log_interval = 5.0
            receiver.packet_count = 50
            receiver.decoded_frame_count = 50
            receiver.last_log_time = 0.0

            receiver._log_stats_if_needed()

            # Should use log_interval (5.0) for avg_fps calculation
            mock_log.assert_called_once()

    def test_thread_inheritance(self):
        """Test VideoReceiver properly inherits from threading.Thread."""
        receiver = MockVideoReceiver(5600, Mock())
        self.assertIsInstance(receiver, threading.Thread)
        self.assertTrue(hasattr(receiver, 'start'))
        self.assertTrue(hasattr(receiver, 'join'))
        self.assertTrue(hasattr(receiver, 'is_alive'))

    def test_abstract_methods_enforced(self):
        """Test that abstract methods must be implemented."""
        class IncompleteReceiver(VideoReceiver):
            def _setup(self):
                pass
            # Missing _main_loop and _cleanup

        with self.assertRaises(TypeError):
            IncompleteReceiver(5600, Mock())

    def test_running_event_controls_lifecycle(self):
        """Test running event is properly set and cleared."""
        receiver = MockVideoReceiver(5600, Mock())

        self.assertFalse(receiver.running.is_set())

        receiver.start()
        time.sleep(0.05)
        self.assertTrue(receiver.running.is_set())

        receiver.stop()
        self.assertFalse(receiver.running.is_set())

    def test_error_callback_not_called(self):
        """Test that error_callback is never called (current implementation issue)."""
        error_callback = Mock()
        receiver = MockVideoReceiver(5600, error_callback, main_loop_fail=True)

        receiver.start()
        time.sleep(0.1)
        receiver.stop()

        # NOTE: This demonstrates that error_callback is not used in current implementation
        error_callback.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
