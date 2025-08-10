import unittest
from unittest.mock import MagicMock, patch
import time

from src.v3xctrl_udp_relay.UDPRelayServer import UDPRelayServer, Role, PortType, Session
from src.v3xctrl_control.message import PeerAnnouncement


class TestUDPRelayServer(unittest.TestCase):
    def setUp(self):
        # Patch SessionStore so no DB is touched
        self.store_patcher = patch("src.v3xctrl_udp_relay.UDPRelayServer.SessionStore")
        self.mock_store_cls = self.store_patcher.start()
        self.mock_store = MagicMock()
        self.mock_store_cls.return_value = self.mock_store

        # Patch socket
        self.socket_patcher = patch("src.v3xctrl_udp_relay.UDPRelayServer.socket.socket")
        self.mock_socket_cls = self.socket_patcher.start()
        self.mock_sock = MagicMock()
        self.mock_socket_cls.return_value = self.mock_sock

        self.server = UDPRelayServer("127.0.0.1", 9999, "fake.db")

    def tearDown(self):
        self.store_patcher.stop()
        self.socket_patcher.stop()

    def test_is_mapping_expired(self):
        now = time.time()
        self.assertTrue(self.server._is_mapping_expired({"ts": now - 99999}, now))
        self.assertFalse(self.server._is_mapping_expired({"ts": now}, now))

    def test_clean_expired_entries_removes_all(self):
        # Prepare expired mappings and sessions
        now = time.time()
        sid = "sess"
        self.server.relay_map = {
            ("1.1.1.1", 1111): {
                "session": sid,
                "role": Role.STREAMER,
                "port_type": PortType.VIDEO,
                "ts": now - 99999,
            },
            ("2.2.2.2", 2222): {
                "session": sid,
                "role": Role.STREAMER,
                "port_type": PortType.CONTROL,
                "ts": now - 99999,
            },
        }
        sess = Session()
        for pt in PortType:
            sess.roles[Role.STREAMER][pt] = type("PeerEntry", (), {"ts": now - 99999})()
        self.server.sessions[sid] = sess

        self.server.running.clear()  # Run loop once
        with patch("time.time", return_value=now):
            # Manually invoke one loop iteration
            self.server.running.set()
            with patch("time.sleep", side_effect=lambda _: self.server.running.clear()):
                self.server._clean_expired_entries()

        self.assertNotIn(sid, self.server.sessions)
        self.assertFalse(self.server.relay_map)

    def test_handle_peer_announcement_invalid_values(self):
        msg = MagicMock()
        msg.get_role.return_value = "bad"
        msg.get_port_type.return_value = "bad"
        self.server._handle_peer_announcement(msg, ("1.1.1.1", 1111))  # should just return

    def test_handle_peer_announcement_unknown_session(self):
        self.mock_store.exists.return_value = False
        msg = MagicMock()
        msg.get_id.return_value = "sess"
        msg.get_role.return_value = Role.STREAMER.value
        msg.get_port_type.return_value = PortType.VIDEO.value
        self.server._handle_peer_announcement(msg, ("1.1.1.1", 1111))
        self.mock_sock.sendto.assert_called()  # sent Error

    def test_handle_peer_announcement_ready_and_mapping(self):
        self.mock_store.exists.return_value = True
        sid = "sess"
        msg = MagicMock(spec=PeerAnnouncement)
        msg.get_id.return_value = sid
        msg.get_role.return_value = Role.STREAMER.value
        msg.get_port_type.return_value = PortType.VIDEO.value

        sess = Session()
        sess.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        sess.register(Role.STREAMER, PortType.CONTROL, ("1.1.1.1", 1112))
        sess.register(Role.VIEWER, PortType.VIDEO, ("2.2.2.2", 2222))
        sess.register(Role.VIEWER, PortType.CONTROL, ("2.2.2.2", 2223))

        self.server.sessions[sid] = sess

        self.server._handle_peer_announcement(msg, ("1.1.1.1", 1111))
        # Mapping should exist for both peers now
        self.assertIn(("1.1.1.1", 1111), self.server.relay_map)
        self.assertIn(("2.2.2.2", 2222), self.server.relay_map)
        self.mock_sock.sendto.assert_called()  # PeerInfo sent

    def test_forward_packet(self):
        target_addr = ("9.9.9.9", 9999)
        self.server.relay_map[("1.1.1.1", 1111)] = {
            "target": target_addr,
            "ts": 0,
            "session": "sess",
            "role": Role.STREAMER,
            "port_type": PortType.VIDEO,
        }
        self.server._forward_packet(b"data", ("1.1.1.1", 1111))
        self.mock_sock.sendto.assert_called_with(b"data", target_addr)
        self.assertGreater(self.server.relay_map[("1.1.1.1", 1111)]["ts"], 0)

    def test_handle_packet_with_peer_announcement(self):
        msg = MagicMock(spec=PeerAnnouncement)
        with patch("src.v3xctrl_udp_relay.UDPRelayServer.Message.from_bytes", return_value=msg):
            data = b"\x83\xa1t\xb0PeerAnnouncement"
            self.server._handle_packet(data, ("1.1.1.1", 1111))

    def test_handle_packet_malformed_announcement(self):
        with patch("src.v3xctrl_udp_relay.UDPRelayServer.Message.from_bytes", side_effect=Exception("bad")):
            data = b"\x83\xa1t\xb0PeerAnnouncement"
            self.server._handle_packet(data, ("1.1.1.1", 1111))  # just logs debug

    def test_handle_packet_forward_existing_mapping(self):
        addr = ("1.1.1.1", 1111)
        self.server.relay_map[addr] = {
            "target": ("2.2.2.2", 2222),
            "ts": 0,
            "session": "sess",
            "role": Role.STREAMER,
            "port_type": PortType.VIDEO,
        }
        self.server._handle_packet(b"payload", addr)
        self.mock_sock.sendto.assert_called_with(b"payload", ("2.2.2.2", 2222))

    def test_shutdown_closes_socket(self):
        self.server.shutdown()
        self.mock_sock.close.assert_called()


if __name__ == "__main__":
    unittest.main()
