import unittest
from unittest.mock import patch, MagicMock
import socket

from src.v3xctrl_udp_relay.Peer import Peer
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
        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch.object(Message, "from_bytes", return_value=pi):
            mock_sock.recvfrom.return_value = (b"data", ("server", 1234))
            result = self.peer._register_with_relay(mock_sock, "video", "client")
            self.assertEqual(result, pi)

    def test_register_with_relay_unauthorized_error(self):
        mock_sock = MagicMock()
        err = MagicMock(spec=Error)
        err.get_error.return_value = "bad auth"
        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch.object(Message, "from_bytes", return_value=err):
            mock_sock.recvfrom.return_value = (b"data", ("server", 1234))
            with self.assertRaises(UnauthorizedError):
                self.peer._register_with_relay(mock_sock, "video", "client")

    def test_register_with_relay_socket_timeout(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [socket.timeout, KeyboardInterrupt]  # to break loop
        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch("time.sleep", return_value=None):
            self.peer._abort_event.set()  # stop immediately after first loop
            try:
                self.peer._register_with_relay(mock_sock, "video", "client")
            except KeyboardInterrupt:
                pass  # expected from fake break
            self.peer._abort_event.clear()

    def test_register_with_relay_generic_exception(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [Exception("boom"), KeyboardInterrupt]
        with patch.object(PeerAnnouncement, "to_bytes", return_value=b"ann"), \
             patch("time.sleep", return_value=None):
            self.peer._abort_event.set()
            try:
                self.peer._register_with_relay(mock_sock, "video", "client")
            except KeyboardInterrupt:
                pass
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
            with self.assertRaises(RuntimeError):
                self.peer._register_all({"video": mock_sock}, "client")

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
