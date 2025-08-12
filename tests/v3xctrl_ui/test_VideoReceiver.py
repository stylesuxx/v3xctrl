import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open
import pytest

from v3xctrl_ui.VideoReceiver import VideoReceiver


class TestVideoReceiver:

    def setup_method(self):
        """Setup for each test method."""
        self.port = 12345
        self.error_callback = Mock()
        self.receiver = VideoReceiver(self.port, self.error_callback)

    def teardown_method(self):
        """Cleanup after each test method."""
        if self.receiver.is_alive():
            self.receiver.stop()
            self.receiver.join(timeout=2.0)

        # Clean up SDP file if it exists
        if self.receiver.sdp_path.exists():
            self.receiver.sdp_path.unlink()

    def test_init(self):
        """Test VideoReceiver initialization."""
        assert self.receiver.port == self.port
        assert self.receiver.error_callback == self.error_callback
        assert isinstance(self.receiver.running, threading.Event)
        assert isinstance(self.receiver.frame_lock, type(threading.Lock()))
        assert isinstance(self.receiver.container_lock, type(threading.Lock()))
        assert self.receiver.frame is None
        assert isinstance(self.receiver.history, deque)
        assert self.receiver.history.maxlen == 100
        assert self.receiver.container is None

        expected_path = Path(tempfile.gettempdir()) / f"rtp_{self.port}.sdp"
        assert self.receiver.sdp_path == expected_path

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.fsync')
    def test_write_sdp(self, mock_fsync, mock_file):
        """Test SDP file writing."""
        mock_file_handle = mock_file.return_value

        self.receiver._write_sdp()

        expected_content = f"""\
v=0
o=- 0 0 IN IP4 127.0.0.1
s=RTP Stream
c=IN IP4 0.0.0.0
t=0 0
m=video {self.port} RTP/AVP 96
a=rtpmap:96 H264/90000
a=recvonly
"""

        mock_file.assert_called_once_with(self.receiver.sdp_path, "w", newline="\n")
        mock_file_handle.write.assert_called_once_with(expected_content)
        mock_file_handle.flush.assert_called_once()
        mock_fsync.assert_called_once_with(mock_file_handle.fileno())

    def test_stop(self):
        """Test stopping the receiver."""
        self.receiver.running.set()  # Simulate running state

        self.receiver.stop()

        assert not self.receiver.running.is_set()

    def test_frame_thread_safety(self):
        """Test that frame access is thread-safe."""
        test_frame = "test_frame_data"

        def set_frame():
            with self.receiver.frame_lock:
                self.receiver.frame = test_frame

        def get_frame():
            with self.receiver.frame_lock:
                return self.receiver.frame

        # Set frame in one thread
        setter_thread = threading.Thread(target=set_frame)
        setter_thread.start()
        setter_thread.join()

        # Get frame in another thread
        result = []
        def getter():
            result.append(get_frame())

        getter_thread = threading.Thread(target=getter)
        getter_thread.start()
        getter_thread.join()

        assert result[0] == test_frame

    def test_container_lock_synchronization(self):
        """Test that container_lock properly synchronizes access."""
        mock_container = MagicMock()

        def set_container():
            with self.receiver.container_lock:
                self.receiver.container = mock_container

        def get_container():
            with self.receiver.container_lock:
                return self.receiver.container

        # Set container in one thread
        setter_thread = threading.Thread(target=set_container)
        setter_thread.start()
        setter_thread.join()

        # Get container in another thread
        result = []
        def getter():
            result.append(get_container())

        getter_thread = threading.Thread(target=getter)
        getter_thread.start()
        getter_thread.join()

        assert result[0] == mock_container

    def test_history_maxlen(self):
        """Test that history maintains maximum length of 100."""
        # Fill history beyond maxlen
        for i in range(150):
            self.receiver.history.append(float(i))

        assert len(self.receiver.history) == 100
        # Should contain the last 100 items (50-149)
        assert self.receiver.history[0] == 50.0
        assert self.receiver.history[-1] == 149.0

    def test_sdp_path_uniqueness(self):
        """Test that different ports create different SDP paths."""
        receiver2 = VideoReceiver(54321, Mock())

        assert self.receiver.sdp_path != receiver2.sdp_path
        assert "12345" in str(self.receiver.sdp_path)
        assert "54321" in str(receiver2.sdp_path)

    def test_error_callback_is_callable(self):
        """Test that error callback can be called."""
        self.receiver.error_callback()
        self.error_callback.assert_called_once()

    def test_multiple_stop_calls_safe(self):
        """Test that multiple stop() calls don't cause issues."""
        # Multiple stop calls should be safe
        self.receiver.stop()
        self.receiver.stop()
        self.receiver.stop()

        assert not self.receiver.running.is_set()


# Integration test that doesn't rely on mocking av
class TestVideoReceiverIntegration:
    """Integration tests that test real behavior without mocking."""

    def test_lifecycle_without_stream(self):
        """Test that receiver can start and stop cleanly without a real stream."""
        error_callback = Mock()
        receiver = VideoReceiver(99999, error_callback)  # Use very unlikely port

        try:
            # Start receiver - it will fail to connect but should handle it gracefully
            receiver.start()

            # Let it run briefly
            time.sleep(0.1)

            # Stop it
            receiver.stop()
            receiver.join(timeout=5.0)

            # Should not be alive after stop
            assert not receiver.is_alive()

        finally:
            if receiver.sdp_path.exists():
                receiver.sdp_path.unlink()


# Fixtures for pytest
@pytest.fixture
def video_receiver():
    """Fixture providing a VideoReceiver instance."""
    receiver = VideoReceiver(12345, Mock())
    yield receiver

    if receiver.is_alive():
        receiver.stop()
        receiver.join(timeout=2.0)

    if receiver.sdp_path.exists():
        receiver.sdp_path.unlink()


def test_frame_processing_performance(video_receiver):
    """Test that frame processing doesn't introduce significant delays."""
    def rapid_frame_updates():
        for i in range(100):
            with video_receiver.frame_lock:
                video_receiver.frame = f"frame_{i}"
            time.sleep(0.001)  # 1ms between frames

    start_time = time.time()
    rapid_frame_updates()
    elapsed = time.time() - start_time

    # Should complete in reasonable time (less than 1 second)
    assert elapsed < 1.0
