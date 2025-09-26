import socket

import unittest
from unittest.mock import patch, MagicMock

from src.v3xctrl_udp_relay.Peer import Peer, PeerRegistrationError
from v3xctrl_control.message import PeerAnnouncement, PeerInfo, Error, Message
from v3xctrl_helper.exceptions import UnauthorizedError


class TestPeer(unittest.TestCase):
    def setUp(self):
        self.peer = Peer("server.test", 1234, "sess123")

    def test_bind_socket(self):
        sock = self.peer._bind_socket("VIDEO")
        self.assertIsInstance(sock, socket.socket)
        sock.close()

    def test_register_with_relay_returns_peerinfo(self):
        mock_sock = MagicMock()
        pi = MagicMock(spec=PeerInfo)
        with (
            patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
            patch.object(Message, "from_bytes", return_value=pi)
        ):
            mock_sock.recvfrom.return_value = (b"data", ("server", 1234))
            self.assertEqual(self.peer._register_with_relay(mock_sock, "video", "client"), pi)

    def test_register_with_relay_unauthorized_error(self):
        mock_sock = MagicMock()
        err = MagicMock(spec=Error)
        err.get_error.return_value = "bad auth"

        with (
            patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
            patch.object(Message, "from_bytes", return_value=err)
        ):
            mock_sock.recvfrom.return_value = (b"data", ("server", 1234))

            with self.assertRaises(UnauthorizedError):
                self.peer._register_with_relay(mock_sock, "video", "client")

    def test_register_with_relay_no_data_received(self):
        """Test branch where recvfrom returns empty data"""
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [
            (b"", ("server", 1234)),  # Empty data - should be skipped
            socket.timeout()  # Then timeout to trigger sleep
        ]

        with (
            patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
            patch("time.sleep", return_value=None)
        ):
            # Set abort event to prevent infinite loop
            self.peer._abort_event.set()

            with self.assertRaises(InterruptedError):
                self.peer._register_with_relay(mock_sock, "video", "client")

        self.peer._abort_event.clear()

    def test_register_with_relay_value_error_parsing(self):
        """Test ValueError handling in message parsing"""
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b"invalid_data", ("server", 1234))

        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch.object(Message, "from_bytes", side_effect=ValueError("Parse error")), \
             patch("time.sleep", return_value=None):
            # Set abort event to prevent infinite loop after the ValueError
            self.peer._abort_event.set()

            with self.assertRaises(InterruptedError):
                self.peer._register_with_relay(mock_sock, "video", "client")

        self.peer._abort_event.clear()

    def test_register_with_relay_unknown_message_type(self):
        """Test handling of unknown message types"""
        mock_sock = MagicMock()
        unknown_msg = MagicMock()  # Not PeerInfo or Error

        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch.object(Message, "from_bytes", return_value=unknown_msg), \
             patch("time.sleep", return_value=None):
            mock_sock.recvfrom.return_value = (b"unknown_msg", ("server", 1234))

            # Set abort event to prevent infinite loop
            self.peer._abort_event.set()

            with self.assertRaises(InterruptedError):
                self.peer._register_with_relay(mock_sock, "video", "client")

        self.peer._abort_event.clear()

    def test_register_with_relay_socket_timeout(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [socket.timeout, KeyboardInterrupt]
        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch("time.sleep", return_value=None):
            self.peer._abort_event.set()

            with self.assertRaises(InterruptedError) as cm:
                self.peer._register_with_relay(mock_sock, "video", "client")

            self.assertIn("video", str(cm.exception))

            self.peer._abort_event.clear()

    def test_register_with_relay_generic_exception(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [Exception("boom"), KeyboardInterrupt]
        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch("time.sleep", return_value=None):
            self.peer._abort_event.set()

            with self.assertRaises(InterruptedError) as cm:
                self.peer._register_with_relay(mock_sock, "video", "client")

            self.assertIn("video", str(cm.exception))

            self.peer._abort_event.clear()

    def test_register_with_relay_abort_event_set(self):
        # Test lines 44-49: abort event handling in registration loop
        mock_sock = MagicMock()

        def side_effect(*args, **kwargs):
            # Set abort event during the first iteration
            self.peer._abort_event.set()
            raise socket.timeout()

        mock_sock.recvfrom.side_effect = side_effect

        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch("time.sleep", return_value=None):

            with self.assertRaises(InterruptedError) as cm:
                self.peer._register_with_relay(mock_sock, "video", "client")

            self.assertIn("video", str(cm.exception))

        self.peer._abort_event.clear()

    def test_register_with_relay_abort_event_checked_on_timeout(self):
        # Test branch 51->36: abort event check after timeout
        mock_sock = MagicMock()

        call_count = 0
        def timeout_then_abort(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: timeout
                raise socket.timeout()
            else:
                # Second call: set abort and timeout again
                self.peer._abort_event.set()
                raise socket.timeout()

        mock_sock.recvfrom.side_effect = timeout_then_abort

        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch("time.sleep", return_value=None):

            with self.assertRaises(InterruptedError) as cm:
                self.peer._register_with_relay(mock_sock, "video", "client")

            self.assertIn("video", str(cm.exception))

        self.peer._abort_event.clear()

    def test_register_with_relay_abort_event_checked_on_exception(self):
        mock_sock = MagicMock()

        call_count = 0
        def exception_then_abort(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: generic exception
                raise Exception("network error")
            else:
                # Second call: set abort and exception again
                self.peer._abort_event.set()
                raise Exception("network error")

        mock_sock.recvfrom.side_effect = exception_then_abort

        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
            patch("time.sleep", return_value=None):

            # Should raise InterruptedError when abort event is set
            with self.assertRaises(InterruptedError) as cm:
                self.peer._register_with_relay(mock_sock, "video", "client")

            self.assertIn("video", str(cm.exception))

        self.peer._abort_event.clear()

    def test_register_with_relay_sendto_exception(self):
        # Test line 73: exception during sendto
        mock_sock = MagicMock()
        mock_sock.sendto.side_effect = OSError("Network unreachable")

        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch("time.sleep", return_value=None):

            # Set abort event to prevent infinite loop
            self.peer._abort_event.set()

            with self.assertRaises(InterruptedError) as cm:
                self.peer._register_with_relay(mock_sock, "video", "client")

            self.assertIn("video", str(cm.exception))

        self.peer._abort_event.clear()

    def test_register_all_success(self):
        mock_sock = MagicMock()
        pi = MagicMock(spec=PeerInfo)
        with patch.object(self.peer, "_register_with_relay", return_value=pi):
            res = self.peer._register_all({"video": mock_sock, "control": mock_sock}, "client")
            self.assertEqual(res["video"], pi)
            self.assertEqual(res["control"], pi)

    def test_register_all_with_exception(self):
        mock_sock = MagicMock()
        with patch.object(self.peer, "_register_with_relay", side_effect=RuntimeError("fail")):
            with self.assertRaises(PeerRegistrationError):
                self.peer._register_all({"video": mock_sock}, "client")

    def test_register_all_mixed_success_and_failure(self):
        """Test partial success scenario"""
        mock_sock1 = MagicMock()
        mock_sock2 = MagicMock()
        pi = MagicMock(spec=PeerInfo)

        def side_effect(sock, port_type, role):
            if port_type == "video":
                return pi
            else:
                raise RuntimeError("Control registration failed")

        with patch.object(self.peer, "_register_with_relay", side_effect=side_effect):
            with self.assertRaises(PeerRegistrationError) as cm:
                self.peer._register_all({"video": mock_sock1, "control": mock_sock2}, "client")

            # Verify that we have both successes and failures
            error = cm.exception
            self.assertEqual(len(error.successes), 1)
            self.assertEqual(len(error.failures), 1)
            self.assertIn("video", error.successes)
            self.assertIn("control", error.failures)

    def test_finalize_sockets(self):
        mock_sock = MagicMock()
        self.peer._finalize_sockets({"video": mock_sock, "control": mock_sock})
        mock_sock.close.assert_any_call()

    def test_setup_success(self):
        pi_video = MagicMock(spec=PeerInfo)
        pi_video.get_ip.return_value = "1.2.3.4"
        pi_video.get_video_port.return_value = 5000
        pi_video.get_control_port.return_value = 6000
        pi_control = MagicMock(spec=PeerInfo)
        pi_control.get_ip.return_value = "5.6.7.8"
        pi_control.get_video_port.return_value = 5001
        pi_control.get_control_port.return_value = 6001

        with patch.object(self.peer, "_bind_socket", return_value=MagicMock(spec=socket.socket)), \
             patch.object(self.peer, "_register_all", return_value={"video": pi_video, "control": pi_control}), \
             patch.object(self.peer, "_finalize_sockets", return_value=None):
            res = self.peer.setup("client", {"video": 1000, "control": 1001})
            self.assertEqual(res["video"], ("1.2.3.4", 5000))
            self.assertEqual(res["control"], ("5.6.7.8", 6001))

    def test_abort_sets_event(self):
        self.assertFalse(self.peer._abort_event.is_set())
        self.peer.abort()
        self.assertTrue(self.peer._abort_event.is_set())


if __name__ == '__main__':
    unittest.main()
