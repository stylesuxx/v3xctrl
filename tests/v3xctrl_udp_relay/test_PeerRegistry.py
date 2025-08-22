import threading
import unittest
from unittest.mock import Mock, patch

from v3xctrl_udp_relay.PeerRegistry import PeerRegistry
from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.custom_types import (
    PeerEntry,
    PortType,
    Role,
    Session,
    SessionNotFoundError,
)


class TestPeerRegistry(unittest.TestCase):
    def setUp(self):
        self.mock_store = Mock(spec=SessionStore)
        self.timeout = 30.0
        self.registry = PeerRegistry(self.mock_store, self.timeout)

    def test_initialization(self):
        self.assertEqual(self.registry.store, self.mock_store)
        self.assertEqual(self.registry.timeout, self.timeout)
        self.assertEqual(self.registry.sessions, {})
        self.assertTrue(hasattr(self.registry.lock, '__enter__'))
        self.assertTrue(hasattr(self.registry.lock, '__exit__'))

    def test_register_peer_session_not_found(self):
        self.mock_store.exists.return_value = False

        result = self.registry.register_peer(
            "session123",
            Role.STREAMER,
            PortType.VIDEO,
            ("192.168.1.1", 8080)
        )

        self.mock_store.exists.assert_called_once_with("session123")
        self.assertIsInstance(result.error, SessionNotFoundError)
        self.assertEqual(str(result.error), "Session 'session123' not found")
        self.assertFalse(result.is_new_peer)
        self.assertFalse(result.session_ready)

    def test_register_peer_new_session_new_peer(self):
        self.mock_store.exists.return_value = True

        result = self.registry.register_peer(
            "session123",
            Role.STREAMER,
            PortType.VIDEO,
            ("192.168.1.1", 8080)
        )

        self.mock_store.exists.assert_called_once_with("session123")
        self.assertIsNone(result.error)
        self.assertTrue(result.is_new_peer)
        self.assertFalse(result.session_ready)
        self.assertIn("session123", self.registry.sessions)

    def test_register_peer_existing_session_new_peer(self):
        self.mock_store.exists.return_value = True
        session = Session()
        session.register(Role.STREAMER, PortType.VIDEO, ("192.168.1.1", 8080))
        self.registry.sessions["session123"] = session

        result = self.registry.register_peer(
            "session123",
            Role.STREAMER,
            PortType.CONTROL,
            ("192.168.1.2", 8081)
        )

        self.assertIsNone(result.error)
        self.assertTrue(result.is_new_peer)
        self.assertFalse(result.session_ready)

    def test_register_peer_existing_peer(self):
        self.mock_store.exists.return_value = True
        session = Session()
        session.register(Role.STREAMER, PortType.VIDEO, ("192.168.1.1", 8080))
        self.registry.sessions["session123"] = session

        result = self.registry.register_peer(
            "session123",
            Role.STREAMER,
            PortType.VIDEO,
            ("192.168.1.2", 8082)
        )

        self.assertIsNone(result.error)
        self.assertFalse(result.is_new_peer)
        self.assertFalse(result.session_ready)

    def test_register_peer_session_becomes_ready(self):
        self.mock_store.exists.return_value = True
        session = Session()
        session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        session.register(Role.STREAMER, PortType.CONTROL, ("1.1.1.2", 1112))
        session.register(Role.VIEWER, PortType.VIDEO, ("2.2.2.1", 2221))
        self.registry.sessions["session123"] = session

        result = self.registry.register_peer(
            "session123",
            Role.VIEWER,
            PortType.CONTROL,
            ("2.2.2.2", 2222)
        )

        self.assertIsNone(result.error)
        self.assertTrue(result.is_new_peer)
        self.assertTrue(result.session_ready)

    def test_register_peer_multiple_sessions(self):
        self.mock_store.exists.return_value = True

        self.registry.register_peer("session1", Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.registry.register_peer("session2", Role.VIEWER, PortType.CONTROL, ("2.2.2.2", 2222))

        self.assertEqual(len(self.registry.sessions), 2)
        self.assertIn("session1", self.registry.sessions)
        self.assertIn("session2", self.registry.sessions)

    def test_register_peer_thread_safety(self):
        self.mock_store.exists.return_value = True
        results = []
        errors = []

        def register_worker(session_id, role, port_type, addr):
            try:
                result = self.registry.register_peer(session_id, role, port_type, addr)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=register_worker,
                args=(f"session{i % 3}", Role.STREAMER, PortType.VIDEO, (f"192.168.1.{i}", 8080 + i))
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 10)
        self.assertLessEqual(len(self.registry.sessions), 3)

    def test_get_session_peers_empty_session(self):
        peers = self.registry.get_session_peers("nonexistent")

        self.assertEqual(peers, {})

    def test_get_session_peers_existing_session(self):
        session = Session()
        session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        session.register(Role.VIEWER, PortType.CONTROL, ("2.2.2.2", 2222))
        self.registry.sessions["session123"] = session

        peers = self.registry.get_session_peers("session123")

        self.assertEqual(len(peers), 2)
        self.assertIn(Role.STREAMER, peers)
        self.assertIn(Role.VIEWER, peers)
        self.assertIn(PortType.VIDEO, peers[Role.STREAMER])
        self.assertIn(PortType.CONTROL, peers[Role.VIEWER])
        self.assertEqual(peers[Role.STREAMER][PortType.VIDEO].addr, ("1.1.1.1", 1111))
        self.assertEqual(peers[Role.VIEWER][PortType.CONTROL].addr, ("2.2.2.2", 2222))

    def test_get_session_peers_returns_same_reference(self):
        session = Session()
        session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.registry.sessions["session123"] = session

        peers1 = self.registry.get_session_peers("session123")
        peers2 = self.registry.get_session_peers("session123")

        self.assertIs(peers1, peers2)
        self.assertEqual(peers1, peers2)

    def test_get_session_peers_allows_modification(self):
        session = Session()
        session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.registry.sessions["session123"] = session

        peers = self.registry.get_session_peers("session123")
        peers[Role.STREAMER][PortType.CONTROL] = PeerEntry(("999.999.999.999", 9999))

        # The modification should affect the original since we return the same reference
        updated_peers = self.registry.get_session_peers("session123")
        self.assertIn(PortType.CONTROL, updated_peers[Role.STREAMER])

    def test_remove_expired_sessions_no_sessions(self):
        self.registry.remove_expired_sessions(set())

        self.assertEqual(len(self.registry.sessions), 0)

    def test_remove_expired_sessions_empty_set(self):
        session = Session()
        session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.registry.sessions["session123"] = session

        self.registry.remove_expired_sessions(set())

        self.assertIn("session123", self.registry.sessions)

    def test_remove_expired_sessions_single_session(self):
        session = Session()
        session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.registry.sessions["session123"] = session

        with patch('logging.info') as mock_log:
            self.registry.remove_expired_sessions({"session123"})

        self.assertNotIn("session123", self.registry.sessions)
        mock_log.assert_called_once_with("session123: Removed expired session")

    def test_remove_expired_sessions_multiple_sessions(self):
        session1 = Session()
        session1.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.registry.sessions["session1"] = session1

        session2 = Session()
        session2.register(Role.VIEWER, PortType.CONTROL, ("2.2.2.2", 2222))
        self.registry.sessions["session2"] = session2

        session3 = Session()
        session3.register(Role.STREAMER, PortType.CONTROL, ("3.3.3.3", 3333))
        self.registry.sessions["session3"] = session3

        with patch('logging.info') as mock_log:
            self.registry.remove_expired_sessions({"session1", "session3"})

        self.assertNotIn("session1", self.registry.sessions)
        self.assertIn("session2", self.registry.sessions)
        self.assertNotIn("session3", self.registry.sessions)

        # Check logging calls
        expected_calls = [
            unittest.mock.call("session1: Removed expired session"),
            unittest.mock.call("session3: Removed expired session")
        ]
        mock_log.assert_has_calls(expected_calls, any_order=True)

    def test_remove_expired_sessions_nonexistent_session(self):
        session1 = Session()
        session1.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.registry.sessions["session1"] = session1

        with patch('logging.info') as mock_log:
            self.registry.remove_expired_sessions({"session1", "nonexistent"})

        self.assertNotIn("session1", self.registry.sessions)
        # Should only log for existing session
        mock_log.assert_called_once_with("session1: Removed expired session")

    def test_remove_expired_sessions_thread_safety(self):
        for i in range(10):
            session = Session()
            session.register(Role.STREAMER, PortType.VIDEO, (f"1.1.1.{i}", 1111))
            self.registry.sessions[f"session{i}"] = session

        results = []
        errors = []

        def remove_worker(session_ids):
            try:
                self.registry.remove_expired_sessions(session_ids)
                results.append(True)
            except Exception as e:
                errors.append(e)

        # Multiple threads removing different sessions
        threads = [
            threading.Thread(target=remove_worker, args=({"session0", "session1", "session2"},)),
            threading.Thread(target=remove_worker, args=({"session3", "session4", "session5"},)),
            threading.Thread(target=remove_worker, args=({"session6", "session7", "session8"},)),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 3)
        # Only session9 should remain
        self.assertEqual(len(self.registry.sessions), 1)
        self.assertIn("session9", self.registry.sessions)

    def test_remove_expired_sessions_concurrent_access(self):
        for i in range(5):
            session = Session()
            session.register(Role.STREAMER, PortType.VIDEO, (f"1.1.1.{i}", 1111))
            self.registry.sessions[f"session{i}"] = session

        results = []
        errors = []

        def register_worker():
            try:
                self.mock_store.exists.return_value = True
                result = self.registry.register_peer("new_session", Role.VIEWER, PortType.VIDEO, ("9.9.9.9", 9999))
                results.append(result)
            except Exception as e:
                errors.append(e)

        def remove_worker():
            try:
                self.registry.remove_expired_sessions({"session0", "session1", "session2"})
                results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_worker),
            threading.Thread(target=remove_worker),
            threading.Thread(target=register_worker),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 3)

    def test_complex_scenario_register_and_remove(self):
        self.mock_store.exists.return_value = True

        # Register multiple sessions
        self.registry.register_peer("session1", Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.registry.register_peer("session1", Role.STREAMER, PortType.CONTROL, ("1.1.1.2", 1112))
        self.registry.register_peer("session2", Role.VIEWER, PortType.CONTROL, ("2.2.2.2", 2222))
        self.registry.register_peer("session3", Role.STREAMER, PortType.VIDEO, ("3.3.3.3", 3333))

        # Verify sessions exist
        self.assertEqual(len(self.registry.sessions), 3)
        peers1 = self.registry.get_session_peers("session1")
        self.assertEqual(len(peers1[Role.STREAMER]), 2)

        # Remove some sessions
        with patch('logging.info') as mock_log:
            self.registry.remove_expired_sessions({"session1", "session3"})

        # Verify correct sessions removed
        self.assertEqual(len(self.registry.sessions), 1)
        self.assertNotIn("session1", self.registry.sessions)
        self.assertIn("session2", self.registry.sessions)
        self.assertNotIn("session3", self.registry.sessions)

        # Verify remaining session data intact
        peers2 = self.registry.get_session_peers("session2")
        self.assertEqual(len(peers2[Role.VIEWER]), 1)
        self.assertEqual(peers2[Role.VIEWER][PortType.CONTROL].addr, ("2.2.2.2", 2222))

        # Verify logging
        expected_calls = [
            unittest.mock.call("session1: Removed expired session"),
            unittest.mock.call("session3: Removed expired session")
        ]
        mock_log.assert_has_calls(expected_calls, any_order=True)

    def test_integration_with_packet_relay_workflow(self):
        """Test the typical workflow with PacketRelay"""
        self.mock_store.exists.return_value = True

        # Register peers for multiple sessions
        self.registry.register_peer("active_session", Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.registry.register_peer("active_session", Role.VIEWER, PortType.VIDEO, ("2.2.2.2", 2222))
        self.registry.register_peer("inactive_session", Role.STREAMER, PortType.CONTROL, ("3.3.3.3", 3333))

        # Simulate PacketRelay determining expired sessions
        expired_sessions = {"inactive_session"}

        # Remove expired sessions
        with patch('logging.info') as mock_log:
            self.registry.remove_expired_sessions(expired_sessions)

        # Verify only active session remains
        self.assertEqual(len(self.registry.sessions), 1)
        self.assertIn("active_session", self.registry.sessions)
        self.assertNotIn("inactive_session", self.registry.sessions)

        # Verify we can still work with the active session
        peers = self.registry.get_session_peers("active_session")
        self.assertEqual(len(peers), 2)  # Both roles present


if __name__ == '__main__':
    unittest.main()
