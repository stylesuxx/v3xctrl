import socket
import threading
import time
import unittest
from unittest.mock import Mock, MagicMock

from v3xctrl_control.message import PeerAnnouncement, PeerInfo
from v3xctrl_tcp.framing import send_message, recv_message
from v3xctrl_udp_relay.ForwardTarget import TcpTarget
from v3xctrl_udp_relay.TCPAcceptor import TCPAcceptor


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestTCPAcceptor(unittest.TestCase):
    def setUp(self):
        self.port = _find_free_port()
        self.stop_event = threading.Event()
        self.relay = MagicMock()

        # Make register_tcp_peer send a PeerInfo response via the TcpTarget
        def fake_register(msg, addr, target):
            peer_info = PeerInfo(ip="1.2.3.4", video_port=8888, control_port=8888)
            target.send(peer_info.to_bytes())

        self.relay.register_tcp_peer.side_effect = fake_register
        self.relay.forward_packet.return_value = []

        self.acceptor = TCPAcceptor(self.port, self.relay, self.stop_event)
        self.acceptor.start()
        time.sleep(0.2)  # Wait for listener to bind

    def tearDown(self):
        self.stop_event.set()
        self.acceptor.stop()

    def _connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(("127.0.0.1", self.port))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return sock

    def test_video_connection_handshake(self):
        sock = self._connect()
        try:
            handshake = PeerAnnouncement(r="viewer", i="sid1", p="video").to_bytes()
            send_message(sock, handshake)

            # Should receive PeerInfo response (sent by our fake_register)
            response = recv_message(sock)
            self.assertIsNotNone(response)

            time.sleep(0.1)
            self.relay.register_tcp_peer.assert_called_once()
            call_args = self.relay.register_tcp_peer.call_args
            msg = call_args[0][0]
            self.assertIsInstance(msg, PeerAnnouncement)
            self.assertEqual(msg.get_port_type(), "video")
        finally:
            sock.close()

    def test_control_connection_forwards_data(self):
        sock = self._connect()
        try:
            handshake = PeerAnnouncement(r="viewer", i="sid1", p="control").to_bytes()
            send_message(sock, handshake)

            # Read PeerInfo response
            response = recv_message(sock)
            self.assertIsNotNone(response)

            # Send control data through the tunnel
            send_message(sock, b"control_data")
            time.sleep(0.2)

            self.relay.forward_packet.assert_called()
            call_args = self.relay.forward_packet.call_args
            self.assertEqual(call_args[0][0], b"control_data")
        finally:
            sock.close()

    def test_disconnect_unregisters(self):
        sock = self._connect()
        handshake = PeerAnnouncement(r="viewer", i="sid1", p="video").to_bytes()
        send_message(sock, handshake)
        recv_message(sock)  # PeerInfo response

        time.sleep(0.1)
        sock.close()
        time.sleep(0.5)

        self.relay.unregister_tcp_peer.assert_called_once()

    def test_invalid_handshake_closes(self):
        sock = self._connect()
        try:
            send_message(sock, b"not a valid message")
            time.sleep(0.3)
            # Connection should be closed by acceptor; register should not be called
            self.relay.register_tcp_peer.assert_not_called()
        finally:
            sock.close()

    def test_streamer_video_forwards_data(self):
        """Streamer video connections read data and forward via relay."""
        sock = self._connect()
        try:
            handshake = PeerAnnouncement(r="streamer", i="sid1", p="video").to_bytes()
            send_message(sock, handshake)

            # Read PeerInfo response
            response = recv_message(sock)
            self.assertIsNotNone(response)

            # Send video data — should be forwarded (not just monitored for disconnect)
            send_message(sock, b"rtp_video_frame_1")
            send_message(sock, b"rtp_video_frame_2")
            time.sleep(0.2)

            self.assertEqual(self.relay.forward_packet.call_count, 2)
            calls = [c[0][0] for c in self.relay.forward_packet.call_args_list]
            self.assertEqual(calls, [b"rtp_video_frame_1", b"rtp_video_frame_2"])
        finally:
            sock.close()

    def test_viewer_video_does_not_forward(self):
        """Viewer video connections only monitor for disconnect, not forward."""
        sock = self._connect()
        try:
            handshake = PeerAnnouncement(r="viewer", i="sid1", p="video").to_bytes()
            send_message(sock, handshake)

            response = recv_message(sock)
            self.assertIsNotNone(response)

            time.sleep(0.2)
            # Viewer video should NOT call forward_packet
            self.relay.forward_packet.assert_not_called()
        finally:
            sock.close()

    def test_streamer_video_disconnect_unregisters(self):
        """Streamer video disconnect triggers unregister."""
        sock = self._connect()
        handshake = PeerAnnouncement(r="streamer", i="sid1", p="video").to_bytes()
        send_message(sock, handshake)
        recv_message(sock)  # PeerInfo response

        time.sleep(0.1)
        sock.close()
        time.sleep(0.5)

        self.relay.unregister_tcp_peer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
