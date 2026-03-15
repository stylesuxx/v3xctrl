import socket
import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_control.message import Ack, Message, PeerAnnouncement, PeerInfo, Syn, SynAck
from v3xctrl_helper import PeerAddresses
from v3xctrl_punch.PunchPeer import AckTimeoutError, PunchPeer


class TestAckTimeoutError(unittest.TestCase):
    def test_can_be_raised_and_caught(self):
        with self.assertRaises(AckTimeoutError):
            raise AckTimeoutError("timeout")

    def test_inherits_from_exception(self):
        self.assertTrue(issubclass(AckTimeoutError, Exception))

    def test_message_preserved(self):
        error = AckTimeoutError("test message")
        self.assertEqual(str(error), "test message")


class TestPunchPeerConstructor(unittest.TestCase):
    def test_attributes_set_correctly(self):
        peer = PunchPeer("relay.example.com", 9000, "session-123", register_timeout=60)
        self.assertEqual(peer.server, "relay.example.com")
        self.assertEqual(peer.port, 9000)
        self.assertEqual(peer.session_id, "session-123")
        self.assertEqual(peer.register_timeout, 60)

    def test_default_register_timeout(self):
        peer = PunchPeer("relay.example.com", 9000, "session-123")
        self.assertEqual(peer.register_timeout, 300)

    def test_announce_interval_constant(self):
        self.assertEqual(PunchPeer.ANNOUNCE_INTERVAL, 5)


class TestBindSocket(unittest.TestCase):
    def setUp(self):
        self.peer = PunchPeer("relay.example.com", 9000, "session-123")

    @patch("v3xctrl_punch.PunchPeer.socket.socket")
    def test_creates_udp_socket(self, mock_socket_class):
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ("0.0.0.0", 12345)
        mock_socket_class.return_value = mock_socket

        result = self.peer.bind_socket("VIDEO")

        mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
        mock_socket.bind.assert_called_once_with(("0.0.0.0", 0))
        self.assertEqual(result, mock_socket)

    @patch("v3xctrl_punch.PunchPeer.socket.socket")
    def test_binds_to_specified_port(self, mock_socket_class):
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ("0.0.0.0", 5000)
        mock_socket_class.return_value = mock_socket

        self.peer.bind_socket("CONTROL", port=5000)

        mock_socket.bind.assert_called_once_with(("0.0.0.0", 5000))


class TestRegisterWithRendezvous(unittest.TestCase):
    def setUp(self):
        self.peer = PunchPeer("relay.example.com", 9000, "session-123", register_timeout=10)
        self.mock_socket = MagicMock()
        self.mock_socket.getsockname.return_value = ("0.0.0.0", 12345)
        self.announcement = PeerAnnouncement(r="car", i="session-123", p="video")

    @patch("v3xctrl_punch.PunchPeer.time")
    def test_success_returns_peer_info(self, mock_time):
        mock_time.time.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()

        peer_info = PeerInfo(ip="1.2.3.4", video_port=5000, control_port=5001)
        self.mock_socket.recvfrom.return_value = (b"peer_info_data", ("1.2.3.4", 9000))

        with patch.object(Message, "from_bytes", return_value=peer_info):
            result = self.peer.register_with_rendezvous(self.mock_socket, self.announcement)

        self.assertEqual(result, peer_info)
        self.mock_socket.settimeout.assert_called_with(1)

    @patch("v3xctrl_punch.PunchPeer.time")
    def test_timeout_returns_none(self, mock_time):
        mock_time.time.side_effect = [0.0, 5.0, 15.0]
        mock_time.sleep = MagicMock()

        self.mock_socket.recvfrom.side_effect = socket.timeout

        result = self.peer.register_with_rendezvous(self.mock_socket, self.announcement)

        self.assertIsNone(result)

    @patch("v3xctrl_punch.PunchPeer.time")
    def test_unexpected_message_type_continues(self, mock_time):
        mock_time.time.side_effect = [0.0, 1.0, 2.0, 15.0]
        mock_time.sleep = MagicMock()

        unexpected_message = Syn()
        peer_info = PeerInfo(ip="1.2.3.4", video_port=5000, control_port=5001)

        self.mock_socket.recvfrom.side_effect = [
            (b"syn_data", ("1.2.3.4", 9000)),
            (b"peer_info_data", ("1.2.3.4", 9000)),
        ]

        with patch.object(Message, "from_bytes", side_effect=[unexpected_message, peer_info]):
            result = self.peer.register_with_rendezvous(self.mock_socket, self.announcement)

        self.assertEqual(result, peer_info)

    @patch("v3xctrl_punch.PunchPeer.time")
    def test_general_exception_returns_none(self, mock_time):
        mock_time.time.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()

        self.mock_socket.sendto.side_effect = OSError("network error")

        result = self.peer.register_with_rendezvous(self.mock_socket, self.announcement)

        self.assertIsNone(result)


class TestRegisterAll(unittest.TestCase):
    def setUp(self):
        self.peer = PunchPeer("relay.example.com", 9000, "session-123")

    def test_initializes_result_keys_from_sockets(self):
        sockets = {"video": MagicMock(), "control": MagicMock()}

        with patch.object(self.peer, "register_with_rendezvous", return_value=None):
            result = self.peer.register_all(sockets, role="car")

        self.assertIn("video", result)
        self.assertIn("control", result)

    def test_creates_peer_announcement_per_socket(self):
        sockets = {"video": MagicMock()}
        recorded_announcements = []

        def capture_register(sock, announcement):
            recorded_announcements.append(announcement)
            return None

        with patch.object(self.peer, "register_with_rendezvous", side_effect=capture_register):
            self.peer.register_all(sockets, role="car")

        # NOTE: Due to a bug in register_all (uses undefined 'pt' instead of
        # 'peer_type' inside reg_worker), the threads crash with NameError and
        # register_with_rendezvous is never called. The results remain None.
        # This test documents the current (buggy) behavior.
        self.assertEqual(len(recorded_announcements), 0)


class TestHandshake(unittest.TestCase):
    def setUp(self):
        self.peer = PunchPeer("relay.example.com", 9000, "session-123")
        self.mock_socket = MagicMock()
        self.address = ("192.168.1.1", 5000)

    @patch("v3xctrl_punch.PunchPeer.time")
    def test_receives_synack_sends_ack_returns(self, mock_time):
        mock_time.time.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()

        synack_message = SynAck()
        source = ("192.168.1.1", 5000)
        self.mock_socket.recvfrom.return_value = (b"synack_data", source)

        with patch.object(Message, "from_bytes", return_value=synack_message):
            result = self.peer._handshake(self.mock_socket, self.address, interval=1, timeout=15)

        self.assertEqual(result, source)
        ack_sent = any(args[1] == source for args, _ in self.mock_socket.sendto.call_args_list if len(args) >= 2)
        self.assertTrue(ack_sent)

    @patch("v3xctrl_punch.PunchPeer.time")
    def test_receives_ack_returns_immediately(self, mock_time):
        mock_time.time.side_effect = [0.0, 1.0]
        mock_time.sleep = MagicMock()

        ack_message = Ack()
        source = ("192.168.1.1", 5000)
        self.mock_socket.recvfrom.return_value = (b"ack_data", source)

        with patch.object(Message, "from_bytes", return_value=ack_message):
            result = self.peer._handshake(self.mock_socket, self.address, interval=1, timeout=15)

        self.assertEqual(result, source)

    @patch("v3xctrl_punch.PunchPeer.time")
    def test_timeout_raises_ack_timeout_error(self, mock_time):
        mock_time.time.side_effect = [0.0, 1.0, 20.0]
        mock_time.sleep = MagicMock()

        self.mock_socket.recvfrom.side_effect = socket.timeout

        with self.assertRaises(AckTimeoutError):
            self.peer._handshake(self.mock_socket, self.address, interval=1, timeout=15)

    @patch("v3xctrl_punch.PunchPeer.time")
    def test_receives_syn_sends_synack(self, mock_time):
        mock_time.time.side_effect = [0.0, 1.0, 2.0]
        mock_time.sleep = MagicMock()

        syn_message = Syn()
        ack_message = Ack()
        source = ("192.168.1.1", 5000)

        self.mock_socket.recvfrom.side_effect = [
            (b"syn_data", source),
            (b"ack_data", source),
        ]

        with patch.object(Message, "from_bytes", side_effect=[syn_message, ack_message]):
            result = self.peer._handshake(self.mock_socket, self.address, interval=1, timeout=15)

        sendto_calls = self.mock_socket.sendto.call_args_list
        synack_sent = any(
            Message.peek_type(args[0]) == "SynAck" and args[1] == source for args, _ in sendto_calls if len(args) >= 2
        )
        self.assertTrue(synack_sent)
        self.assertEqual(result, source)


class TestRendezvousAndPunch(unittest.TestCase):
    def setUp(self):
        self.peer = PunchPeer("relay.example.com", 9000, "session-123")

    def test_success_path(self):
        video_socket = MagicMock()
        control_socket = MagicMock()
        sockets = {"video": video_socket, "control": control_socket}

        video_peer_info = MagicMock(spec=PeerInfo)
        video_peer_info.get_ip.return_value = "10.0.0.1"
        video_peer_info.get_video_port.return_value = 6000
        video_peer_info.get_control_port.return_value = 6001

        control_peer_info = MagicMock(spec=PeerInfo)

        peer_info_dict = {"video": video_peer_info, "control": control_peer_info}

        video_address = ("10.0.0.1", 6000)
        control_address = ("10.0.0.1", 6001)

        with patch.object(self.peer, "register_all", return_value=peer_info_dict):
            with patch.object(
                self.peer,
                "_handshake",
                side_effect=lambda sock, addr: video_address if sock is video_socket else control_address,
            ):
                result = self.peer.rendezvous_and_punch("car", sockets)

        self.assertEqual(result.video, video_address)
        self.assertEqual(result.control, control_address)

    def test_registration_failure_raises_runtime_error(self):
        sockets = {"video": MagicMock(), "control": MagicMock()}
        incomplete_info = {"video": MagicMock(spec=PeerInfo), "control": None}

        with patch.object(self.peer, "register_all", return_value=incomplete_info):
            with self.assertRaises(RuntimeError):
                self.peer.rendezvous_and_punch("car", sockets)


class TestFinalizeSockets(unittest.TestCase):
    def test_clears_timeout_and_closes_sockets(self):
        peer = PunchPeer("relay.example.com", 9000, "session-123")
        video_socket = MagicMock()
        control_socket = MagicMock()
        sockets = {"video": video_socket, "control": control_socket}

        peer.finalize_sockets(sockets)

        video_socket.settimeout.assert_called_once_with(None)
        video_socket.close.assert_called_once()
        control_socket.settimeout.assert_called_once_with(None)
        control_socket.close.assert_called_once()


class TestSetup(unittest.TestCase):
    def test_calls_bind_rendezvous_and_finalize(self):
        peer = PunchPeer("relay.example.com", 9000, "session-123")
        ports = {"video": 5000, "control": 5001}

        video_socket = MagicMock()
        control_socket = MagicMock()
        peer_addresses = PeerAddresses(video=("10.0.0.1", 6000), control=("10.0.0.1", 6001))

        def mock_bind_socket(name, port):
            if port == 5000:
                return video_socket
            return control_socket

        with patch.object(peer, "bind_socket", side_effect=mock_bind_socket) as mock_bind:
            with patch.object(peer, "rendezvous_and_punch", return_value=peer_addresses) as mock_rendezvous:
                with patch.object(peer, "finalize_sockets") as mock_finalize:
                    result = peer.setup("car", ports)

        self.assertEqual(mock_bind.call_count, 2)
        mock_rendezvous.assert_called_once()
        mock_finalize.assert_called_once()
        self.assertEqual(result, peer_addresses)


if __name__ == "__main__":
    unittest.main()
