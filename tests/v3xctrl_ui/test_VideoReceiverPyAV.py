import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, call, mock_open, patch

import av
import numpy as np

from v3xctrl_ui.VideoReceiverPyAV import VideoReceiverPyAV


class TestVideoReceiverPyAVInit(unittest.TestCase):

    def test_initialization(self):
        error_callback = Mock()
        receiver = VideoReceiverPyAV(5600, error_callback)

        self.assertEqual(receiver.port, 5600)
        self.assertEqual(receiver.error_callback, error_callback)
        self.assertTrue(str(receiver.sdp_path).endswith("rtp_5600.sdp"))
        self.assertIsNone(receiver.container)
        self.assertTrue(hasattr(receiver.container_lock, 'acquire'))
        self.assertTrue(hasattr(receiver.container_lock, 'release'))
        self.assertEqual(receiver.max_age_seconds, 0.5)
        self.assertIsNone(receiver.latest_packet_pts)
        self.assertEqual(receiver.dropped_old_frames, 0)

    def test_thread_count_configuration(self):
        with patch('os.cpu_count', return_value=8):
            receiver = VideoReceiverPyAV(5600, Mock())
            self.assertEqual(receiver.thread_count, "4")

        with patch('os.cpu_count', return_value=2):
            receiver = VideoReceiverPyAV(5600, Mock())
            self.assertEqual(receiver.thread_count, "2")

        with patch('os.cpu_count', return_value=None):
            receiver = VideoReceiverPyAV(5600, Mock())
            self.assertEqual(receiver.thread_count, "1")

    def test_container_options(self):
        receiver = VideoReceiverPyAV(5600, Mock())
        expected_options = {
            "fflags": "nobuffer+flush_packets+discardcorrupt",
            "protocol_whitelist": "file,udp,rtp",
            "analyzeduration": "100000",
            "probesize": "2048",
        }
        self.assertEqual(receiver.container_options, expected_options)

    def test_codec_options(self):
        receiver = VideoReceiverPyAV(5600, Mock())
        self.assertEqual(receiver.codec_options["flags"], "low_delay")
        self.assertEqual(receiver.codec_options["flags2"], "fast")
        self.assertIn("threads", receiver.codec_options)


class TestVideoReceiverPyAVSdpFile(unittest.TestCase):

    def setUp(self):
        self.receiver = VideoReceiverPyAV(5600, Mock())

    def test_write_sdp_creates_correct_content(self):
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('os.fsync') as mock_fsync:
                self.receiver._write_sdp()

                mock_file.assert_called_once_with(self.receiver.sdp_path, "w", newline="\n")
                handle = mock_file.return_value.__enter__.return_value

                written_content = ''.join(call.args[0] for call in handle.write.call_args_list)

                self.assertIn("m=video 5600 RTP/AVP 96", written_content)
                self.assertIn("a=rtpmap:96 H264/90000", written_content)
                self.assertIn("v=0", written_content)
                self.assertIn("s=RTP Stream", written_content)

                handle.flush.assert_called_once()
                mock_fsync.assert_called_once()

    def test_setup_calls_write_sdp(self):
        with patch.object(self.receiver, '_write_sdp') as mock_write_sdp:
            self.receiver._setup()
            mock_write_sdp.assert_called_once()

    def test_sdp_path_includes_port(self):
        receiver1 = VideoReceiverPyAV(5600, Mock())
        receiver2 = VideoReceiverPyAV(5601, Mock())

        self.assertIn("5600", str(receiver1.sdp_path))
        self.assertIn("5601", str(receiver2.sdp_path))
        self.assertNotEqual(receiver1.sdp_path, receiver2.sdp_path)


class TestVideoReceiverPyAVCleanup(unittest.TestCase):

    def setUp(self):
        self.receiver = VideoReceiverPyAV(5600, Mock())

    def test_cleanup_closes_container(self):
        mock_container = Mock()
        self.receiver.container = mock_container

        self.receiver._cleanup()

        mock_container.close.assert_called_once()
        self.assertIsNone(self.receiver.container)

    def test_cleanup_handles_container_close_exception(self):
        mock_container = Mock()
        mock_container.close.side_effect = Exception("Close failed")
        self.receiver.container = mock_container

        with patch('logging.warning') as mock_warning:
            self.receiver._cleanup()

            mock_warning.assert_called()
            self.assertIsNone(self.receiver.container)

    def test_cleanup_removes_sdp_file(self):
        with patch.object(self.receiver, 'sdp_path') as mock_path:
            mock_path.exists.return_value = True
            self.receiver._cleanup()
            mock_path.unlink.assert_called_once()

    def test_cleanup_handles_sdp_removal_exception(self):
        with patch.object(self.receiver, 'sdp_path') as mock_path:
            mock_path.exists.return_value = True
            mock_path.unlink.side_effect = Exception("Unlink failed")
            with patch('logging.warning') as mock_warning:
                self.receiver._cleanup()
                mock_warning.assert_called()

    def test_cleanup_no_container(self):
        self.receiver.container = None
        self.receiver._cleanup()  # Should not raise exception

    def test_cleanup_no_sdp_file(self):
        with patch.object(self.receiver, 'sdp_path') as mock_path:
            mock_path.exists.return_value = False
            self.receiver._cleanup()  # Should not raise exception


class TestVideoReceiverPyAVPacketDropping(unittest.TestCase):

    def setUp(self):
        self.receiver = VideoReceiverPyAV(5600, Mock())
        self.mock_stream = Mock(spec=av.VideoStream)
        self.mock_stream.time_base = 1.0 / 90000  # Typical H.264 time base

    def test_should_drop_packet_no_pts(self):
        packet = Mock(spec=av.Packet)
        packet.pts = None

        result = self.receiver._should_drop_packet_by_age(packet, self.mock_stream)

        self.assertFalse(result)
        self.assertIsNone(self.receiver.latest_packet_pts)

    def test_should_drop_packet_first_packet(self):
        packet = Mock(spec=av.Packet)
        packet.pts = 90000  # 1 second worth of PTS

        result = self.receiver._should_drop_packet_by_age(packet, self.mock_stream)

        self.assertFalse(result)
        self.assertEqual(self.receiver.latest_packet_pts, 90000)

    def test_should_drop_packet_newer_packet_within_threshold(self):
        self.receiver.latest_packet_pts = 90000  # 1 second

        packet = Mock(spec=av.Packet)
        packet.pts = 85000  # 0.944 seconds - within 0.5s threshold

        result = self.receiver._should_drop_packet_by_age(packet, self.mock_stream)

        self.assertFalse(result)
        self.assertEqual(self.receiver.dropped_old_frames, 0)

    def test_should_drop_packet_old_packet_beyond_threshold(self):
        self.receiver.latest_packet_pts = 90000  # 1 second

        packet = Mock(spec=av.Packet)
        packet.pts = 45000  # 0.5 seconds - exactly at threshold (might be dropped)

        result = self.receiver._should_drop_packet_by_age(packet, self.mock_stream)
        self.assertTrue(result)

    def test_should_drop_packet_very_old_packet(self):
        self.receiver.latest_packet_pts = 90000  # 1 second

        packet = Mock(spec=av.Packet)
        packet.pts = 0  # Very old packet

        result = self.receiver._should_drop_packet_by_age(packet, self.mock_stream)
        self.assertTrue(result)


class TestVideoReceiverPyAVMainLoop(unittest.TestCase):

    def setUp(self):
        self.receiver = VideoReceiverPyAV(5600, Mock())
        self.receiver.running = threading.Event()
        self.receiver.running.set()

    def test_main_loop_container_open_failure_retry(self):
        with patch('av.open', side_effect=av.AVError(-1, "Open failed", "")):
            with patch('time.sleep') as mock_sleep:
                with patch('logging.warning') as mock_warning:
                    # Stop after first retry
                    def stop_after_retry(*args):
                        self.receiver.running.clear()

                    mock_sleep.side_effect = stop_after_retry
                    self.receiver._main_loop()

                    mock_warning.assert_called()
                    mock_sleep.assert_called_with(0.5)

    def test_main_loop_container_open_success(self):
        mock_container = Mock()
        mock_stream = Mock(spec=av.VideoStream)
        mock_stream.codec_context = Mock()
        mock_stream.time_base = 1.0 / 90000
        mock_container.streams.video = [mock_stream]

        # Make demux return empty to avoid packet processing
        mock_container.demux.return_value = []

        call_count = 0
        def mock_open(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Stop after first successful open
                self.receiver.running.clear()
            return mock_container

        with patch('av.open', side_effect=mock_open):
            with patch('time.sleep'):
                self.receiver._main_loop()

                # Container should have been set (briefly) during execution
                self.assertEqual(mock_stream.codec_context.options, self.receiver.codec_options)

    def test_main_loop_packet_processing(self):
        mock_container = Mock()
        mock_stream = Mock(spec=av.VideoStream)
        mock_stream.codec_context = Mock()
        mock_stream.time_base = 1.0 / 90000
        mock_container.streams.video = [mock_stream]

        # Create mock packets
        mock_packet1 = Mock(spec=av.Packet)
        mock_packet1.pts = 90000  # 1 second
        mock_packet2 = Mock(spec=av.Packet)
        mock_packet2.pts = 180000  # 2 seconds

        # Mock frames
        mock_frame1 = Mock()
        mock_frame2 = Mock()
        mock_frame1.to_ndarray.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_frame2.to_ndarray.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

        mock_packet1.decode.return_value = [mock_frame1]
        mock_packet2.decode.return_value = [mock_frame2]

        packets = [mock_packet1, mock_packet2]

        # Make demux return packets once, then stop
        call_count = 0
        def mock_demux(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return packets
            else:
                self.receiver.running.clear()
                return []

        mock_container.demux.side_effect = mock_demux

        with patch('av.open', return_value=mock_container):
            with patch.object(self.receiver, '_update_frame') as mock_update:
                with patch.object(self.receiver, '_log_stats_if_needed'):
                    self.receiver._main_loop()

                    self.assertEqual(mock_update.call_count, 2)
                    self.assertEqual(self.receiver.packet_count, 2)

    def test_main_loop_empty_decode(self):
        mock_container = Mock()
        mock_stream = Mock(spec=av.VideoStream)
        mock_stream.codec_context = Mock()
        mock_stream.time_base = 1.0 / 90000
        mock_container.streams.video = [mock_stream]

        mock_packet = Mock(spec=av.Packet)
        mock_packet.pts = 90000
        mock_packet.decode.return_value = []  # Empty decode

        # Make demux return packet once, then stop
        call_count = 0
        def mock_demux(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [mock_packet]
            else:
                self.receiver.running.clear()
                return []

        mock_container.demux.side_effect = mock_demux

        with patch('av.open', return_value=mock_container):
            with patch.object(self.receiver, '_log_stats_if_needed'):
                self.receiver._main_loop()

                self.assertEqual(self.receiver.dropped_empty_frames, 1)

    def test_main_loop_unexpected_error_handling(self):
        mock_container = Mock()
        mock_stream = Mock(spec=av.VideoStream)
        mock_stream.codec_context = Mock()
        mock_stream.time_base = 1.0 / 90000
        mock_container.streams.video = [mock_stream]

        # Make demux raise an unexpected error
        def error_demux(*args):
            self.receiver.running.clear()  # Stop after error
            raise RuntimeError("Unexpected error")

        mock_container.demux.side_effect = error_demux

        with patch('av.open', return_value=mock_container):
            with patch('logging.exception') as mock_exception:
                self.receiver._main_loop()

                mock_exception.assert_called()
                mock_container.close.assert_called()

    def test_main_loop_frame_cleared_on_exit(self):
        mock_container = Mock()
        mock_stream = Mock(spec=av.VideoStream)
        mock_stream.codec_context = Mock()
        mock_stream.time_base = 1.0 / 90000
        mock_container.streams.video = [mock_stream]

        # Make demux return empty and stop immediately
        def empty_demux(*args):
            self.receiver.running.clear()
            return []

        mock_container.demux.side_effect = empty_demux

        self.receiver.frame = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch('av.open', return_value=mock_container):
            self.receiver._main_loop()

            self.assertIsNone(self.receiver.frame)


class TestVideoReceiverPyAVIntegration(unittest.TestCase):

    def test_full_lifecycle_with_mocked_av(self):
        error_callback = Mock()
        receiver = VideoReceiverPyAV(5600, error_callback)

        mock_container = Mock()
        mock_stream = Mock(spec=av.VideoStream)
        mock_stream.codec_context = Mock()
        mock_stream.time_base = 1.0 / 90000
        mock_container.streams.video = [mock_stream]
        mock_container.demux.return_value = []

        with patch('builtins.open', mock_open()):
            with patch('os.fsync'):
                with patch('av.open', return_value=mock_container):
                    with patch.object(receiver, 'sdp_path') as mock_path:
                        mock_path.exists.return_value = True
                        receiver.start()
                        time.sleep(0.1)
                        receiver.stop()

        error_callback.assert_not_called()
        mock_container.close.assert_called()

    def test_real_file_operations(self):
        """Test with real file operations to ensure SDP writing works."""
        receiver = VideoReceiverPyAV(5600, Mock())

        # Use a temporary directory we control
        with tempfile.TemporaryDirectory() as temp_dir:
            receiver.sdp_path = Path(temp_dir) / "test_rtp_5600.sdp"

            receiver._setup()

            self.assertTrue(receiver.sdp_path.exists())

            content = receiver.sdp_path.read_text()
            self.assertIn("m=video 5600 RTP/AVP 96", content)
            self.assertIn("a=rtpmap:96 H264/90000", content)

            receiver._cleanup()

            self.assertFalse(receiver.sdp_path.exists())

    def test_thread_safety_container_operations(self):
        """Test thread safety of container operations."""
        receiver = VideoReceiverPyAV(5600, Mock())
        errors = []

        def container_operations():
            try:
                for i in range(50):
                    with receiver.container_lock:
                        receiver.container = Mock()
                        time.sleep(0.001)
                        receiver.container = None
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=container_operations) for _ in range(3)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(len(errors), 0)

    def test_stats_accumulation(self):
        """Test that statistics are properly accumulated."""
        receiver = VideoReceiverPyAV(5600, Mock())

        # Simulate packet processing
        receiver.packet_count = 100
        receiver.empty_decode_count = 20
        receiver.dropped_old_frames = 5

        # These should accumulate properly
        self.assertEqual(receiver.packet_count, 100)
        self.assertEqual(receiver.empty_decode_count, 20)
        self.assertEqual(receiver.dropped_old_frames, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
