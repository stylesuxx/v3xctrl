import socket
import unittest
from unittest.mock import Mock, patch, MagicMock

from v3xctrl_control.message import PeerAnnouncement
from v3xctrl_udp_relay.PacketRelay import PacketRelay
from v3xctrl_udp_relay.ForwardTarget import TcpTarget, UdpTarget
from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.custom_types import PortType, Session, Role


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

    def test_unregister_tcp_peer(self):
        addr = ("10.0.0.1", 50000)
        target = Mock(spec=TcpTarget)
        self.relay.tcp_targets[addr] = target

        self.relay.unregister_tcp_peer(addr)
        self.assertNotIn(addr, self.relay.tcp_targets)

    def test_unregister_tcp_peer_not_found(self):
        self.relay.unregister_tcp_peer(("10.0.0.1", 99999))  # Should not raise

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

    def test_forward_packet_uses_tcp_target(self):
        streamer_addr = ("10.0.0.1", 50000)
        viewer_addr = ("10.0.0.2", 50001)

        tcp_target = Mock(spec=TcpTarget)
        tcp_target.is_alive.return_value = True
        tcp_target.send.return_value = True
        self.relay.tcp_targets[viewer_addr] = tcp_target

        # Set up mapping: streamer -> viewer
        self.relay.mappings[streamer_addr] = ({viewer_addr}, 0)

        result = self.relay.forward_packet(b"video_frame", streamer_addr)

        self.assertTrue(result)
        tcp_target.send.assert_called_once_with(b"video_frame")
        # Should NOT have called sock.sendto
        self.mock_sock.sendto.assert_not_called()

    def test_forward_packet_uses_udp_for_non_tcp_peer(self):
        streamer_addr = ("10.0.0.1", 50000)
        viewer_addr = ("10.0.0.2", 50001)

        self.relay.mappings[streamer_addr] = ({viewer_addr}, 0)

        result = self.relay.forward_packet(b"video_frame", streamer_addr)

        self.assertTrue(result)
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


if __name__ == "__main__":
    unittest.main()
