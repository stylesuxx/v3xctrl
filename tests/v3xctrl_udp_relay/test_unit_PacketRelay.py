import socket
import time
import unittest
from unittest.mock import Mock, patch

from v3xctrl_udp_relay.PacketRelay import PacketRelay
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

    def test_cleanup_expired_mappings_with_session_not_found_in_get_sid(self) -> None:
        expired_addr = ("192.168.1.99", 9999)
        target_addr = ("192.168.1.100", 9900)
        old_time = time.time() - self.timeout - 1

        with self.relay.mapping_lock:
            self.relay.mappings[expired_addr] = (target_addr, old_time)

        with patch('logging.info') as mock_log:
            self.relay.cleanup_expired_mappings()

        mock_log.assert_called()

        with self.relay.mapping_lock:
            self.assertNotIn(expired_addr, self.relay.mappings)

    def test_cleanup_expired_mappings_session_not_in_sessions_dict(self) -> None:
        session = Session("test_session")
        addr = ("192.168.1.10", 5000)
        session.register(Role.STREAMER, PortType.VIDEO, addr)
        self.relay.sessions["test_session"] = session

        target_addr = ("192.168.1.20", 6000)
        old_time = time.time() - self.timeout - 1

        with self.relay.mapping_lock:
            self.relay.mappings[addr] = (target_addr, old_time)

        del self.relay.sessions["test_session"]

        with patch('logging.info') as mock_log:
            self.relay.cleanup_expired_mappings()

        mock_log.assert_called()

    def test_cleanup_expired_mappings_empty_affected_sessions(self) -> None:
        addr = ("192.168.1.10", 5000)
        target_addr = ("192.168.1.20", 6000)
        current_time = time.time()

        with self.relay.mapping_lock:
            self.relay.mappings[addr] = (target_addr, current_time)

        with patch('logging.info') as mock_log:
            self.relay.cleanup_expired_mappings()

        with self.relay.mapping_lock:
            self.assertIn(addr, self.relay.mappings)

    def test_cleanup_orphaned_sessions_ready_session_not_removed(self) -> None:
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

        self.assertIn("test_session", self.relay.sessions)


if __name__ == "__main__":
    unittest.main()
