import socket
import unittest
from unittest.mock import Mock

from v3xctrl_control.message import PeerAnnouncement
from v3xctrl_relay.custom_types import PortType, Role, Session
from v3xctrl_relay.ForwardTarget import TcpTarget, UdpTarget
from v3xctrl_relay.PacketRelay import Mapping, PacketRelay
from v3xctrl_relay.SessionStore import SessionStore
from v3xctrl_tcp import Transport


class TestPacketRelayTcp(unittest.TestCase):
    def setUp(self):
        self.mock_store = Mock(spec=SessionStore)
        self.mock_sock = Mock(spec=socket.socket)
        self.relay = PacketRelay(
            store=self.mock_store,
            sock=self.mock_sock,
            address=("1.2.3.4", 8888),
            timeout=300,
        )

    def test_register_tcp_peer_stores_target(self):
        addr = ("10.0.0.1", 50000)
        target = Mock(spec=TcpTarget)
        msg = PeerAnnouncement(r="viewer", i="sid1", p="video")

        self.mock_store.exists.return_value = True
        self.relay.register_tcp_peer(msg, addr, target)

        self.assertIn(addr, self.relay.tcp_targets)
        self.assertIs(self.relay.tcp_targets[addr], target)

    def test_dead_tcp_target_stays_in_dict(self):
        """Dead TcpTarget stays in tcp_targets so forward_packet
        doesn't fall through to UDP after disconnect."""
        addr = ("10.0.0.1", 50000)
        target = Mock(spec=TcpTarget)
        target.is_alive.return_value = False
        self.relay.tcp_targets[addr] = target

        self.assertIn(addr, self.relay.tcp_targets)

    def test_get_target_returns_tcp_when_registered(self):
        addr = ("10.0.0.1", 50000)
        tcp_target = Mock(spec=TcpTarget)
        tcp_target.is_alive.return_value = True
        self.relay.tcp_targets[addr] = tcp_target

        target = self.relay._get_target(addr)
        self.assertIs(target, tcp_target)

    def test_get_target_returns_udp_when_no_tcp(self):
        addr = ("10.0.0.1", 50000)
        target = self.relay._get_target(addr)
        self.assertIsInstance(target, UdpTarget)

    def test_get_target_returns_udp_when_tcp_dead(self):
        addr = ("10.0.0.1", 50000)
        tcp_target = Mock(spec=TcpTarget)
        tcp_target.is_alive.return_value = False
        self.relay.tcp_targets[addr] = tcp_target

        target = self.relay._get_target(addr)
        self.assertIsInstance(target, UdpTarget)

    def test_forward_packet_defers_tcp_target(self):
        streamer_addr = ("10.0.0.1", 50000)
        viewer_addr = ("10.0.0.2", 50001)

        tcp_target = Mock(spec=TcpTarget)
        tcp_target.is_alive.return_value = True
        self.relay.tcp_targets[viewer_addr] = tcp_target

        # Set up mapping: streamer -> viewer
        self.relay.mappings[streamer_addr] = Mapping({viewer_addr}, 0)

        deferred = self.relay.forward_packet(b"video_frame", streamer_addr)

        self.assertIsNotNone(deferred)
        self.assertEqual(deferred, [tcp_target])
        # TCP send is deferred - not called by forward_packet
        tcp_target.send.assert_not_called()
        self.mock_sock.sendto.assert_not_called()

    def test_forward_packet_sends_udp_inline(self):
        streamer_addr = ("10.0.0.1", 50000)
        viewer_addr = ("10.0.0.2", 50001)

        self.relay.mappings[streamer_addr] = Mapping({viewer_addr}, 0)

        deferred = self.relay.forward_packet(b"video_frame", streamer_addr)

        self.assertIsNotNone(deferred)
        self.assertEqual(deferred, [])
        self.mock_sock.sendto.assert_called_once_with(b"video_frame", viewer_addr)

    def test_send_peer_info_uses_tcp_target(self):
        viewer_addr = ("10.0.0.2", 50001)
        tcp_target = Mock(spec=TcpTarget)
        tcp_target.is_alive.return_value = True
        tcp_target.send.return_value = True
        self.relay.tcp_targets[viewer_addr] = tcp_target

        session = Session("sid1")
        session.register(Role.STREAMER, PortType.VIDEO, ("10.0.0.1", 50000))
        session.register(Role.STREAMER, PortType.CONTROL, ("10.0.0.1", 50002))
        session.register(Role.VIEWER, PortType.VIDEO, viewer_addr)
        session.register(Role.VIEWER, PortType.CONTROL, ("10.0.0.2", 50003))

        self.relay._send_peer_info(session)

        # TCP target should have been called for viewer's video address
        tcp_target.send.assert_called()

    def test_cleanup_removes_dead_tcp_targets(self):
        dead_addr = ("10.0.0.1", 50000)
        alive_addr = ("10.0.0.2", 50001)

        dead_target = Mock(spec=TcpTarget)
        dead_target.is_alive.return_value = False
        alive_target = Mock(spec=TcpTarget)
        alive_target.is_alive.return_value = True

        self.relay.tcp_targets[dead_addr] = dead_target
        self.relay.tcp_targets[alive_addr] = alive_target

        self.relay.cleanup_expired_mappings()

        self.assertNotIn(dead_addr, self.relay.tcp_targets)
        self.assertIn(alive_addr, self.relay.tcp_targets)

    def test_streamer_tcp_viewer_udp_forwarding(self):
        """Streamer registers via TCP, viewer via UDP, data flows correctly."""
        streamer_video = ("10.0.0.1", 50000)
        streamer_control = ("10.0.0.1", 50002)
        viewer_video = ("10.0.0.2", 50001)
        viewer_control = ("10.0.0.2", 50003)

        # Register streamer via TCP
        streamer_video_target = Mock(spec=TcpTarget)
        streamer_video_target.is_alive.return_value = True
        streamer_control_target = Mock(spec=TcpTarget)
        streamer_control_target.is_alive.return_value = True

        self.mock_store.exists.return_value = True

        self.relay.register_tcp_peer(
            PeerAnnouncement(r="streamer", i="sid1", p="video"),
            streamer_video, streamer_video_target
        )
        self.relay.register_tcp_peer(
            PeerAnnouncement(r="streamer", i="sid1", p="control"),
            streamer_control, streamer_control_target
        )

        # Register viewer via UDP
        self.relay.register_peer(
            PeerAnnouncement(r="viewer", i="sid1", p="video"),
            viewer_video
        )
        self.relay.register_peer(
            PeerAnnouncement(r="viewer", i="sid1", p="control"),
            viewer_control
        )

        # Reset mocks after registration (PeerInfo sends happen during setup)
        self.mock_sock.sendto.reset_mock()
        streamer_video_target.send.reset_mock()
        streamer_control_target.send.reset_mock()

        # Forward video from streamer -> viewer via UDP (inline send)
        deferred = self.relay.forward_packet(b"video_data", streamer_video)
        self.assertEqual(deferred, [])
        self.mock_sock.sendto.assert_called_with(b"video_data", viewer_video)

        # Forward control from viewer -> streamer via TCP (deferred)
        self.mock_sock.sendto.reset_mock()
        deferred = self.relay.forward_packet(b"control_cmd", viewer_control)
        self.assertEqual(deferred, [streamer_control_target])
        streamer_control_target.send.assert_not_called()
        self.mock_sock.sendto.assert_not_called()

    def test_streamer_tcp_viewer_tcp_forwarding(self):
        """Both streamer and viewer on TCP, relay bridges TCP↔TCP."""
        streamer_video = ("10.0.0.1", 50000)
        streamer_control = ("10.0.0.1", 50002)
        viewer_video = ("10.0.0.2", 50001)
        viewer_control = ("10.0.0.2", 50003)

        self.mock_store.exists.return_value = True

        # Register streamer via TCP
        streamer_video_target = Mock(spec=TcpTarget)
        streamer_video_target.is_alive.return_value = True
        streamer_control_target = Mock(spec=TcpTarget)
        streamer_control_target.is_alive.return_value = True

        self.relay.register_tcp_peer(
            PeerAnnouncement(r="streamer", i="sid1", p="video"),
            streamer_video, streamer_video_target
        )
        self.relay.register_tcp_peer(
            PeerAnnouncement(r="streamer", i="sid1", p="control"),
            streamer_control, streamer_control_target
        )

        # Register viewer via TCP
        viewer_video_target = Mock(spec=TcpTarget)
        viewer_video_target.is_alive.return_value = True
        viewer_control_target = Mock(spec=TcpTarget)
        viewer_control_target.is_alive.return_value = True

        self.relay.register_tcp_peer(
            PeerAnnouncement(r="viewer", i="sid1", p="video"),
            viewer_video, viewer_video_target
        )
        self.relay.register_tcp_peer(
            PeerAnnouncement(r="viewer", i="sid1", p="control"),
            viewer_control, viewer_control_target
        )

        # Reset mocks after registration (PeerInfo sends happen during setup)
        self.mock_sock.sendto.reset_mock()
        streamer_video_target.send.reset_mock()
        streamer_control_target.send.reset_mock()
        viewer_video_target.send.reset_mock()
        viewer_control_target.send.reset_mock()

        # Forward video from streamer -> viewer via TCP (deferred)
        deferred = self.relay.forward_packet(b"video_data", streamer_video)
        self.assertEqual(deferred, [viewer_video_target])
        viewer_video_target.send.assert_not_called()
        self.mock_sock.sendto.assert_not_called()

        # Forward control from viewer -> streamer via TCP (deferred)
        deferred = self.relay.forward_packet(b"control_cmd", viewer_control)
        self.assertEqual(deferred, [streamer_control_target])
        streamer_control_target.send.assert_not_called()

    def test_peer_transport_tracked_on_register(self):
        """Transport is recorded on PeerEntry after registration."""
        tcp_addr = ("10.0.0.1", 50000)
        udp_addr = ("10.0.0.2", 50001)

        self.mock_store.exists.return_value = True

        # TCP registration
        tcp_target = Mock(spec=TcpTarget)
        self.relay.register_tcp_peer(
            PeerAnnouncement(r="streamer", i="sid1", p="video"),
            tcp_addr, tcp_target
        )

        session = self.relay.sessions["sid1"]
        entry = session.roles[Role.STREAMER][PortType.VIDEO]
        self.assertEqual(entry.transport, Transport.TCP)

        # UDP registration
        self.relay.register_peer(
            PeerAnnouncement(r="viewer", i="sid1", p="video"),
            udp_addr
        )

        entry = session.roles[Role.VIEWER][PortType.VIDEO]
        self.assertEqual(entry.transport, Transport.UDP)


if __name__ == "__main__":
    unittest.main()
