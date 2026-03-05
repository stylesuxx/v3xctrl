import socket
import time
import unittest
from unittest.mock import Mock, patch

from v3xctrl_udp_relay.PacketRelay import Mapping, PacketRelay
from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.custom_types import Role, PortType, Session


class TestPacketRelay(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_store = Mock(spec=SessionStore)
        self.mock_sock = Mock(spec=socket.socket)
        self.address = ("127.0.0.1", 12345)
        self.timeout = 5.0
        self.relay = PacketRelay(
            store=self.mock_store,
            sock=self.mock_sock,
            address=self.address,
            timeout=self.timeout
        )

    def test_get_sid_for_address_unlocked_no_sessions(self) -> None:
        addr = ("192.168.1.10", 5000)

        sids = self.relay._get_sids_for_address_unlocked(addr)
        self.assertEqual(len(sids), 0)

    def test_get_sid_for_address_unlocked_address_not_found(self) -> None:
        session = Session("test_session")
        session.register(
            Role.STREAMER,
            PortType.VIDEO,
            ("192.168.1.10", 5000)
        )
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

        session.register(
            Role.STREAMER,
            PortType.VIDEO,
            ("192.168.1.10", 5000)
        )
        session.register(
            Role.VIEWER,
            PortType.VIDEO,
            ("192.168.1.20", 6000)
        )
        session.register(
            Role.VIEWER,
            PortType.CONTROL,
            ("192.168.1.20", 6001)
        )

        initial_mappings_count = len(self.relay.mappings)
        self.relay._update_mappings(session)

        self.assertEqual(len(self.relay.mappings), initial_mappings_count)

    def test_update_mappings_incomplete_viewer_ports(self) -> None:
        session = Session("test_session")

        session.register(
            Role.STREAMER,
            PortType.VIDEO,
            ("192.168.1.10", 5000)
        )
        session.register(
            Role.STREAMER,
            PortType.CONTROL,
            ("192.168.1.10", 5001)
        )
        session.register(
            Role.VIEWER,
            PortType.VIDEO,
            ("192.168.1.20", 6000)
        )

        initial_mappings_count = len(self.relay.mappings)
        self.relay._update_mappings(session)

        self.assertEqual(len(self.relay.mappings), initial_mappings_count)

    def test_update_mappings_missing_port_type_in_roles(self) -> None:
        session = Session("test_session")

        session.register(
            Role.STREAMER,
            PortType.VIDEO,
            ("192.168.1.10", 5000)
        )
        session.register(
            Role.STREAMER,
            PortType.CONTROL,
            ("192.168.1.10", 5001)
        )
        session.register(
            Role.VIEWER,
            PortType.VIDEO,
            ("192.168.1.20", 6000)
        )
        session.register(
            Role.VIEWER,
            PortType.CONTROL,
            ("192.168.1.20", 6001)
        )

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

        with patch('logging.info') as mock_log:
            self.relay.cleanup_expired_mappings()

        with self.relay.mapping_lock:
            self.assertIn(addr, self.relay.mappings)

    def test_cleanup_orphaned_sessions_ready_session_removed(self) -> None:
        session = Session("test_session")
        old_time = time.time() - self.timeout - 1

        session.register(
            Role.STREAMER,
            PortType.VIDEO,
            ("192.168.1.10", 5000)
        )
        session.register(
            Role.STREAMER,
            PortType.CONTROL,
            ("192.168.1.10", 5001)
        )
        session.register(
            Role.VIEWER,
            PortType.VIDEO,
            ("192.168.1.20", 6000)
        )
        session.register(
            Role.VIEWER,
            PortType.CONTROL,
            ("192.168.1.20", 6001)
        )

        session.last_announcement_at = old_time
        self.relay.sessions["test_session"] = session

        with patch('time.time', return_value=time.time()):
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
        self.relay.register_peer(
            PeerAnnouncement(r="spectator", i="test_session", p="video"),
            spectator_video
        )
        self.relay.register_peer(
            PeerAnnouncement(r="spectator", i="test_session", p="control"),
            spectator_control
        )

        self.assertIn(spectator_video, self.relay.spectator_by_address)
        self.assertIn(spectator_control, self.relay.spectator_by_address)
        self.assertIs(
            self.relay.spectator_by_address[spectator_video],
            self.relay.spectator_by_address[spectator_control]
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
        self.relay.register_peer(
            PeerAnnouncement(r="spectator", i="test_session", p="video"),
            spectator_video
        )
        self.relay.register_peer(
            PeerAnnouncement(r="spectator", i="test_session", p="control"),
            spectator_control
        )

        self.assertIn(spectator_video, self.relay.spectator_by_address)

        # Re-register as viewer - should remove spectator from index
        self.relay.register_peer(
            PeerAnnouncement(r="viewer", i="test_session", p="video"),
            spectator_video
        )

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
        self.relay.register_peer(
            PeerAnnouncement(r="spectator", i="test_session", p="video"),
            spectator_video
        )
        self.relay.register_peer(
            PeerAnnouncement(r="spectator", i="test_session", p="control"),
            spectator_control
        )

        old_time = self.relay.spectator_by_address[spectator_video].last_announcement_at

        with patch('time.time', return_value=old_time + 10):
            self.relay.update_spectator_heartbeat(spectator_control)

        new_time = self.relay.spectator_by_address[spectator_video].last_announcement_at
        self.assertEqual(new_time, old_time + 10)

    def test_spectator_heartbeat_unknown_address_noop(self) -> None:
        unknown_addr = ("192.168.1.99", 9999)
        self.relay.update_spectator_heartbeat(unknown_addr)  # Should not raise


if __name__ == "__main__":
    unittest.main()
