import socket
import time
import unittest
from unittest.mock import Mock, patch

from v3xctrl_relay.custom_types import PortType, Role, Session
from v3xctrl_relay.ForwardTarget import TcpTarget
from v3xctrl_relay.PacketRelay import Mapping, PacketRelay
from v3xctrl_relay.SessionStore import SessionStore


class TestPacketRelay(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_store = Mock(spec=SessionStore)
        self.mock_sock = Mock(spec=socket.socket)
        self.address = ("127.0.0.1", 12345)
        self.timeout = 5.0
        self.relay = PacketRelay(store=self.mock_store, sock=self.mock_sock, address=self.address, timeout=self.timeout)

    def test_get_sid_for_address_unlocked_no_sessions(self) -> None:
        addr = ("192.168.1.10", 5000)

        sids = self.relay._get_sids_for_address_unlocked(addr)
        self.assertEqual(len(sids), 0)

    def test_get_sid_for_address_unlocked_address_not_found(self) -> None:
        session = Session("test_session")
        session.register(Role.STREAMER, PortType.VIDEO, ("192.168.1.10", 5000))
        self.relay.sessions["test_session"] = session

        addr = ("192.168.1.99", 9999)
        sids = self.relay._get_sids_for_address_unlocked(addr)
        self.assertEqual(len(sids), 0)

    def test_get_sid_for_address_unlocked_found(self) -> None:
        addr = ("192.168.1.10", 5000)
        session = Session("test_session")
        session.register(Role.STREAMER, PortType.VIDEO, addr)
        self.relay.sessions["test_session"] = session

        sids = self.relay._get_sids_for_address_unlocked(addr)
        self.assertGreater(len(sids), 0)
        self.assertEqual(sids.pop(), "test_session")

    def test_update_mappings_incomplete_streamer_ports(self) -> None:
        session = Session("test_session")

        session.register(Role.STREAMER, PortType.VIDEO, ("192.168.1.10", 5000))
        session.register(Role.VIEWER, PortType.VIDEO, ("192.168.1.20", 6000))
        session.register(Role.VIEWER, PortType.CONTROL, ("192.168.1.20", 6001))

        initial_mappings_count = len(self.relay.mappings)
        self.relay._update_mappings(session)

        self.assertEqual(len(self.relay.mappings), initial_mappings_count)

    def test_update_mappings_incomplete_viewer_ports(self) -> None:
        session = Session("test_session")

        session.register(Role.STREAMER, PortType.VIDEO, ("192.168.1.10", 5000))
        session.register(Role.STREAMER, PortType.CONTROL, ("192.168.1.10", 5001))
        session.register(Role.VIEWER, PortType.VIDEO, ("192.168.1.20", 6000))

        initial_mappings_count = len(self.relay.mappings)
        self.relay._update_mappings(session)

        self.assertEqual(len(self.relay.mappings), initial_mappings_count)

    def test_update_mappings_missing_port_type_in_roles(self) -> None:
        session = Session("test_session")

        session.register(Role.STREAMER, PortType.VIDEO, ("192.168.1.10", 5000))
        session.register(Role.STREAMER, PortType.CONTROL, ("192.168.1.10", 5001))
        session.register(Role.VIEWER, PortType.VIDEO, ("192.168.1.20", 6000))
        session.register(Role.VIEWER, PortType.CONTROL, ("192.168.1.20", 6001))

        del session.roles[Role.STREAMER][PortType.CONTROL]

        initial_mappings_count = len(self.relay.mappings)
        self.relay._update_mappings(session)

        self.assertEqual(len(self.relay.mappings), initial_mappings_count)

    def test_cleanup_expired_mappings_session_not_in_sessions_dict(self) -> None:
        session = Session("test_session")
        addr = ("192.168.1.10", 5000)
        session.register(Role.STREAMER, PortType.VIDEO, addr)
        self.relay.sessions["test_session"] = session

        target_addr = ("192.168.1.20", 6000)
        old_time = time.time() - self.timeout - 1

        with self.relay.mapping_lock:
            self.relay.mappings[addr] = Mapping(target_addr, old_time)

        del self.relay.sessions["test_session"]

        self.relay.cleanup_expired_mappings()

    def test_cleanup_expired_mappings_empty_affected_sessions(self) -> None:
        addr = ("192.168.1.10", 5000)
        target_addr = ("192.168.1.20", 6000)
        current_time = time.time()

        with self.relay.mapping_lock:
            self.relay.mappings[addr] = Mapping(target_addr, current_time)

        with patch("logging.info") as _mock_log:
            self.relay.cleanup_expired_mappings()

        with self.relay.mapping_lock:
            self.assertIn(addr, self.relay.mappings)

    def test_cleanup_orphaned_sessions_ready_session_removed(self) -> None:
        session = Session("test_session")
        old_time = time.time() - self.timeout - 1

        session.register(Role.STREAMER, PortType.VIDEO, ("192.168.1.10", 5000))
        session.register(Role.STREAMER, PortType.CONTROL, ("192.168.1.10", 5001))
        session.register(Role.VIEWER, PortType.VIDEO, ("192.168.1.20", 6000))
        session.register(Role.VIEWER, PortType.CONTROL, ("192.168.1.20", 6001))

        session.last_announcement_at = old_time
        self.relay.sessions["test_session"] = session

        with patch("time.time", return_value=time.time()):
            self.relay.cleanup_expired_mappings()

        self.assertNotIn("test_session", self.relay.sessions)

    def test_remove_spectator_does_not_mutate_existing_targets_set(self) -> None:
        """Removing a spectator must create a new targets set, not mutate the
        existing one. forward_packet holds a reference to the old set outside
        the lock - mutating it causes RuntimeError during iteration."""
        session = Session("test_session")
        streamer_video = ("192.168.1.10", 5000)
        streamer_control = ("192.168.1.10", 5001)
        viewer_video = ("192.168.1.20", 6000)
        viewer_control = ("192.168.1.20", 6001)
        spectator_video = ("192.168.1.30", 7000)
        spectator_control = ("192.168.1.30", 7001)

        session.register(Role.STREAMER, PortType.VIDEO, streamer_video)
        session.register(Role.STREAMER, PortType.CONTROL, streamer_control)
        session.register(Role.VIEWER, PortType.VIDEO, viewer_video)
        session.register(Role.VIEWER, PortType.CONTROL, viewer_control)
        session.register(Role.SPECTATOR, PortType.VIDEO, spectator_video)
        session.register(Role.SPECTATOR, PortType.CONTROL, spectator_control)

        self.relay.sessions["test_session"] = session
        self.relay._update_mappings(session)
        self.relay._setup_spectator_mappings(session, spectator_video)

        # Grab reference to the targets set (simulates what forward_packet does)
        with self.relay.mapping_lock:
            old_targets = self.relay.mappings[streamer_video].targets

        self.assertIn(spectator_video, old_targets)

        # Remove spectator
        spectator_addrs = {spectator_video, spectator_control}
        with self.relay.mapping_lock:
            self.relay._remove_spectator_from_mappings(spectator_addrs, session)

        # Old reference must still contain the spectator (not mutated)
        self.assertIn(spectator_video, old_targets)

        # New mapping must not contain the spectator
        with self.relay.mapping_lock:
            new_targets = self.relay.mappings[streamer_video].targets
        self.assertNotIn(spectator_video, new_targets)

    def test_spectator_reverse_index_populated_on_register(self) -> None:
        self.mock_store.exists.return_value = True
        self.mock_store.get_session_id_from_spectator_id.return_value = "test_session"

        session = Session("test_session")
        streamer_video = ("192.168.1.10", 5000)
        streamer_control = ("192.168.1.10", 5001)
        viewer_video = ("192.168.1.20", 6000)
        viewer_control = ("192.168.1.20", 6001)

        session.register(Role.STREAMER, PortType.VIDEO, streamer_video)
        session.register(Role.STREAMER, PortType.CONTROL, streamer_control)
        session.register(Role.VIEWER, PortType.VIDEO, viewer_video)
        session.register(Role.VIEWER, PortType.CONTROL, viewer_control)

        self.relay.sessions["test_session"] = session
        self.relay._update_mappings(session)

        spectator_video = ("192.168.1.30", 7000)
        spectator_control = ("192.168.1.30", 7001)

        from v3xctrl_control.message import PeerAnnouncement

        self.relay.register_peer(PeerAnnouncement(r="spectator", i="test_session", p="video"), spectator_video)
        self.relay.register_peer(PeerAnnouncement(r="spectator", i="test_session", p="control"), spectator_control)

        self.assertIn(spectator_video, self.relay.spectator_by_address)
        self.assertIn(spectator_control, self.relay.spectator_by_address)
        self.assertIs(
            self.relay.spectator_by_address[spectator_video], self.relay.spectator_by_address[spectator_control]
        )

    def test_spectator_reverse_index_cleared_on_removal(self) -> None:
        self.mock_store.exists.return_value = True
        self.mock_store.get_session_id_from_spectator_id.return_value = "test_session"

        session = Session("test_session")
        streamer_video = ("192.168.1.10", 5000)
        streamer_control = ("192.168.1.10", 5001)
        viewer_video = ("192.168.1.20", 6000)
        viewer_control = ("192.168.1.20", 6001)

        session.register(Role.STREAMER, PortType.VIDEO, streamer_video)
        session.register(Role.STREAMER, PortType.CONTROL, streamer_control)
        session.register(Role.VIEWER, PortType.VIDEO, viewer_video)
        session.register(Role.VIEWER, PortType.CONTROL, viewer_control)

        self.relay.sessions["test_session"] = session
        self.relay._update_mappings(session)

        spectator_video = ("192.168.1.30", 7000)
        spectator_control = ("192.168.1.30", 7001)

        from v3xctrl_control.message import PeerAnnouncement

        self.relay.register_peer(PeerAnnouncement(r="spectator", i="test_session", p="video"), spectator_video)
        self.relay.register_peer(PeerAnnouncement(r="spectator", i="test_session", p="control"), spectator_control)

        self.assertIn(spectator_video, self.relay.spectator_by_address)

        # Re-register as viewer - should remove spectator from index
        self.relay.register_peer(PeerAnnouncement(r="viewer", i="test_session", p="video"), spectator_video)

        self.assertNotIn(spectator_video, self.relay.spectator_by_address)
        self.assertNotIn(spectator_control, self.relay.spectator_by_address)

    def test_spectator_heartbeat_updates_via_reverse_index(self) -> None:
        self.mock_store.exists.return_value = True
        self.mock_store.get_session_id_from_spectator_id.return_value = "test_session"

        session = Session("test_session")
        streamer_video = ("192.168.1.10", 5000)
        streamer_control = ("192.168.1.10", 5001)
        viewer_video = ("192.168.1.20", 6000)
        viewer_control = ("192.168.1.20", 6001)

        session.register(Role.STREAMER, PortType.VIDEO, streamer_video)
        session.register(Role.STREAMER, PortType.CONTROL, streamer_control)
        session.register(Role.VIEWER, PortType.VIDEO, viewer_video)
        session.register(Role.VIEWER, PortType.CONTROL, viewer_control)

        self.relay.sessions["test_session"] = session
        self.relay._update_mappings(session)

        spectator_video = ("192.168.1.30", 7000)
        spectator_control = ("192.168.1.30", 7001)

        from v3xctrl_control.message import PeerAnnouncement

        self.relay.register_peer(PeerAnnouncement(r="spectator", i="test_session", p="video"), spectator_video)
        self.relay.register_peer(PeerAnnouncement(r="spectator", i="test_session", p="control"), spectator_control)

        old_time = self.relay.spectator_by_address[spectator_video].last_announcement_at

        with patch("time.time", return_value=old_time + 10):
            self.relay.update_spectator_heartbeat(spectator_control)

        new_time = self.relay.spectator_by_address[spectator_video].last_announcement_at
        self.assertEqual(new_time, old_time + 10)

    def test_spectator_heartbeat_unknown_address_noop(self) -> None:
        unknown_addr = ("192.168.1.99", 9999)
        self.relay.update_spectator_heartbeat(unknown_addr)  # Should not raise


class TestForwardPacket(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_store = Mock(spec=SessionStore)
        self.mock_sock = Mock(spec=socket.socket)
        self.address = ("127.0.0.1", 12345)
        self.timeout = 5.0
        self.relay = PacketRelay(store=self.mock_store, sock=self.mock_sock, address=self.address, timeout=self.timeout)

        self.source_addr = ("192.168.1.10", 5000)
        self.target_udp_1 = ("192.168.1.20", 6000)
        self.target_udp_2 = ("192.168.1.30", 7000)
        self.target_tcp = ("192.168.1.40", 8000)

    def test_returns_none_for_unknown_source(self) -> None:
        result = self.relay.forward_packet(b"data", ("192.168.1.99", 9999))
        self.assertIsNone(result)

    def test_updates_source_mapping_timestamp(self) -> None:
        old_time = time.time() - 100
        with self.relay.mapping_lock:
            self.relay.mappings[self.source_addr] = Mapping({self.target_udp_1}, old_time)

        self.relay.forward_packet(b"data", self.source_addr)

        with self.relay.mapping_lock:
            new_time = self.relay.mappings[self.source_addr].timestamp
        self.assertGreater(new_time, old_time + 50)

    def test_does_not_update_target_mapping_timestamp(self) -> None:
        old_time = time.time() - 100
        with self.relay.mapping_lock:
            self.relay.mappings[self.source_addr] = Mapping({self.target_udp_1}, time.time())
            self.relay.mappings[self.target_udp_1] = Mapping({self.source_addr}, old_time)

        self.relay.forward_packet(b"data", self.source_addr)

        with self.relay.mapping_lock:
            target_time = self.relay.mappings[self.target_udp_1].timestamp
        self.assertAlmostEqual(target_time, old_time, delta=1.0)

    def test_sends_to_all_udp_targets_inline(self) -> None:
        with self.relay.mapping_lock:
            self.relay.mappings[self.source_addr] = Mapping({self.target_udp_1, self.target_udp_2}, time.time())

        self.relay.forward_packet(b"data", self.source_addr)

        sent_addrs = {call[0][1] for call in self.mock_sock.sendto.call_args_list}
        self.assertIn(self.target_udp_1, sent_addrs)
        self.assertIn(self.target_udp_2, sent_addrs)

    def test_skips_dead_tcp_target_no_udp_fallback(self) -> None:
        dead_target = Mock(spec=TcpTarget)
        dead_target.is_alive.return_value = False
        with self.relay.mapping_lock:
            self.relay.tcp_targets[self.target_tcp] = dead_target
            self.relay.mappings[self.source_addr] = Mapping({self.target_tcp}, time.time())

        deferred = self.relay.forward_packet(b"data", self.source_addr)

        self.assertIsNotNone(deferred)
        self.assertEqual(len(deferred), 0)
        # Must not fall back to UDP for a dead TCP target
        for call_args in self.mock_sock.sendto.call_args_list:
            self.assertNotEqual(call_args[0][1], self.target_tcp)

    def test_returns_alive_tcp_targets_as_deferred(self) -> None:
        alive_target = Mock(spec=TcpTarget)
        alive_target.is_alive.return_value = True
        with self.relay.mapping_lock:
            self.relay.tcp_targets[self.target_tcp] = alive_target
            self.relay.mappings[self.source_addr] = Mapping({self.target_tcp}, time.time())

        deferred = self.relay.forward_packet(b"data", self.source_addr)

        self.assertIsNotNone(deferred)
        self.assertEqual(len(deferred), 1)
        self.assertIs(deferred[0], alive_target)
        # TCP target send is deferred, not called inline
        alive_target.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
