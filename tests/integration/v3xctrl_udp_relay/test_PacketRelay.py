import socket
import threading
import time
import unittest
from unittest.mock import Mock, patch


from v3xctrl_helper import Address
from v3xctrl_control.message import PeerAnnouncement
from v3xctrl_udp_relay.PacketRelay import PacketRelay
from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.custom_types import (
    Role,
    PortType,
)


class TestPacketRelayIntegration(unittest.TestCase):
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

        self.streamer_video_addr = ("192.168.1.10", 5000)
        self.streamer_control_addr = ("192.168.1.10", 5001)
        self.viewer_video_addr = ("192.168.1.20", 6000)
        self.viewer_control_addr = ("192.168.1.20", 6001)

        self.session_id = "test_session_123"

    # helper to announce (creates a PeerAnnouncement-like mock)
    def _announce(self, sid: str, role: Role, port_type: PortType, addr: Address):
        msg = PeerAnnouncement(role.value, sid, port_type.value)
        self.relay.register_peer(msg, addr)

    def test_complete_session_workflow(self) -> None:
        """
        Test complete workflow:
        - register peers (via PeerAnnouncement mocks)
        - session becomes ready
        - mappings created and forwarding works (relay uses relay.sock)
        """
        self.mock_store.exists.return_value = True

        # Register streamer peers
        self._announce(self.session_id, Role.STREAMER, PortType.VIDEO, self.streamer_video_addr)
        self._announce(self.session_id, Role.STREAMER, PortType.CONTROL, self.streamer_control_addr)

        # Register viewer peers
        self._announce(self.session_id, Role.VIEWER, PortType.VIDEO, self.viewer_video_addr)
        self._announce(self.session_id, Role.VIEWER, PortType.CONTROL, self.viewer_control_addr)

        # Session should be present and ready
        self.assertIn(self.session_id, self.relay.sessions)
        session = self.relay.sessions[self.session_id]
        self.assertTrue(session.is_ready())

        # Verify peers structure
        peers = self.relay.get_session_peers(self.session_id)
        self.assertEqual(len(peers), 2)
        self.assertEqual(len(peers[Role.STREAMER]), 2)
        self.assertEqual(len(peers[Role.VIEWER]), 2)

        # Verify mappings created (inspect mapping dict under lock)
        with self.relay.mapping_lock:
            self.assertIn(self.streamer_video_addr, self.relay.mappings)
            target, _ = self.relay.mappings[self.streamer_video_addr]
            self.assertEqual(target, self.viewer_video_addr)

        # Forwarding: calling forward_packet should use relay.sock (self.mock_sock)
        self.mock_sock.reset_mock()
        self.relay.forward_packet(b"video_data", self.streamer_video_addr)
        self.mock_sock.sendto.assert_called_once_with(b"video_data", self.viewer_video_addr)

        # Control direction
        self.mock_sock.reset_mock()
        self.relay.forward_packet(b"control_data", self.viewer_control_addr)
        self.mock_sock.sendto.assert_called_once_with(b"control_data", self.streamer_control_addr)

    def test_session_not_found_error(self) -> None:
        """Test registration when session doesn't exist in store."""
        self.mock_store.exists.return_value = False
        sid = "nonexistent_session"

        msg = Mock(spec=PeerAnnouncement)
        msg.get_id.return_value = sid
        msg.get_role.return_value = Role.STREAMER.value
        msg.get_port_type.return_value = PortType.VIDEO.value

        self.relay.register_peer(msg, self.streamer_video_addr)

        # PacketRelay sends an Error back to the announcing addr via self.sock
        self.mock_sock.sendto.assert_called_once()
        sent_bytes, target = self.mock_sock.sendto.call_args[0]
        self.assertEqual(target, self.streamer_video_addr)
        self.assertIsInstance(sent_bytes, (bytes, bytearray))

    def test_duplicate_peer_registration(self) -> None:
        self.mock_store.exists.return_value = True

        msg = Mock(spec=PeerAnnouncement)
        msg.get_id.return_value = self.session_id
        msg.get_role.return_value = Role.STREAMER.value
        msg.get_port_type.return_value = PortType.VIDEO.value

        # First registration
        self.relay.register_peer(msg, self.streamer_video_addr)
        before = self.relay.get_session_peers(self.session_id)

        # Duplicate registration (same announcement)
        self.relay.register_peer(msg, self.streamer_video_addr)
        after = self.relay.get_session_peers(self.session_id)

        self.assertEqual(before, after)

    def test_packet_forwarding_with_timestamp_update(self) -> None:
        """Test that packet forwarding updates timestamps for timeout tracking."""
        self.mock_store.exists.return_value = True

        initial_time = 1_600_000_000.0
        # create mappings with a deterministic timestamp
        with patch('time.time', return_value=initial_time):
            self._announce(self.session_id, Role.STREAMER, PortType.VIDEO, self.streamer_video_addr)
            self._announce(self.session_id, Role.STREAMER, PortType.CONTROL, self.streamer_control_addr)
            self._announce(self.session_id, Role.VIEWER, PortType.VIDEO, self.viewer_video_addr)
            self._announce(self.session_id, Role.VIEWER, PortType.CONTROL, self.viewer_control_addr)

        # Verify initial timestamp
        with self.relay.mapping_lock:
            _, initial_timestamp = self.relay.mappings[self.streamer_video_addr]
            self.assertEqual(initial_timestamp, initial_time)

        # Forward packet at a later time and ensure timestamp is updated and packet sent
        later_time = initial_time + 2.0
        with patch('time.time', return_value=later_time):
            self.mock_sock.reset_mock()
            self.relay.forward_packet(b"data", self.streamer_video_addr)
            self.mock_sock.sendto.assert_called_once_with(b"data", self.viewer_video_addr)

        # Verify mapping timestamp updated
        with self.relay.mapping_lock:
            _, updated_timestamp = self.relay.mappings[self.streamer_video_addr]
            self.assertEqual(updated_timestamp, later_time)

    def test_packet_forwarding_unknown_address(self) -> None:
        """Packet for unknown address should be dropped."""
        unknown_addr = ("192.168.1.99", 9999)

        self.relay.forward_packet(b"data", unknown_addr)

        # relay.sock should not have been used
        self.mock_sock.sendto.assert_not_called()

    def test_cleanup_orphaned_sessions(self) -> None:
        """Test cleanup of sessions that never became ready."""
        self.mock_store.exists.return_value = True

        # Register incomplete session (only streamer video)
        self._announce(self.session_id, Role.STREAMER, PortType.VIDEO, self.streamer_video_addr)

        # Ensure session exists
        peers = self.relay.get_session_peers(self.session_id)
        self.assertGreater(len(peers), 0)

        # Advance time past timeout so orphaned session will be removed
        future = time.time() + self.timeout + 1
        with patch('time.time', return_value=future):
            with patch('logging.info') as mock_log:
                self.relay.cleanup_expired_mappings()
                mock_log.assert_called()

        # Session should be removed
        peers_after = self.relay.get_session_peers(self.session_id)
        self.assertEqual(len(peers_after), 0)

    def test_cleanup_expired_mappings(self) -> None:
        """Test cleanup of expired mappings and associated sessions."""
        self.mock_store.exists.return_value = True

        initial_time = 1_600_000_000.0
        with patch('time.time', return_value=initial_time):
            self._announce(self.session_id, Role.STREAMER, PortType.VIDEO, self.streamer_video_addr)
            self._announce(self.session_id, Role.STREAMER, PortType.CONTROL, self.streamer_control_addr)
            self._announce(self.session_id, Role.VIEWER, PortType.VIDEO, self.viewer_video_addr)
            self._announce(self.session_id, Role.VIEWER, PortType.CONTROL, self.viewer_control_addr)

        # Ensure mapping exists (do not change mapping timestamp)
        with self.relay.mapping_lock:
            self.assertIn(self.streamer_video_addr, self.relay.mappings)

        # Forward a packet at the same patched time (so timestamp stays predictable)
        with patch('time.time', return_value=initial_time):
            self.mock_sock.reset_mock()
            self.relay.forward_packet(b"data", self.streamer_video_addr)
            self.assertEqual(self.mock_sock.sendto.call_count, 1)

        # Fast forward past timeout so mappings expire
        expired_time = initial_time + self.timeout + 1
        with patch('time.time', return_value=expired_time):
            with patch('logging.info') as mock_log:
                self.relay.cleanup_expired_mappings()
                self.assertGreater(mock_log.call_count, 0)

        # Mappings should be removed (no forwarding)
        self.mock_sock.reset_mock()
        self.relay.forward_packet(b"data", self.streamer_video_addr)
        self.mock_sock.sendto.assert_not_called()

        # Session should be cleaned up
        peers = self.relay.get_session_peers(self.session_id)
        self.assertEqual(len(peers), 0)

    def test_session_overwrite_on_new_ready_session(self) -> None:
        """Test that new ready sessions overwrite old mappings for same addresses."""
        self.mock_store.exists.return_value = True

        # Set up first complete session
        self._announce(self.session_id, Role.STREAMER, PortType.VIDEO, self.streamer_video_addr)
        self._announce(self.session_id, Role.STREAMER, PortType.CONTROL, self.streamer_control_addr)
        self._announce(self.session_id, Role.VIEWER, PortType.VIDEO, self.viewer_video_addr)
        self._announce(self.session_id, Role.VIEWER, PortType.CONTROL, self.viewer_control_addr)

        # Verify initial forwarding target
        self.mock_sock.reset_mock()
        self.relay.forward_packet(b"data", self.streamer_video_addr)
        self.mock_sock.sendto.assert_called_once_with(b"data", self.viewer_video_addr)

        # Create new session with same streamer addresses but different viewer
        new_session_id = "new_session_456"
        new_viewer_video_addr = ("192.168.1.30", 7000)
        new_viewer_control_addr = ("192.168.1.30", 7001)

        self._announce(new_session_id, Role.STREAMER, PortType.VIDEO, self.streamer_video_addr)
        self._announce(new_session_id, Role.STREAMER, PortType.CONTROL, self.streamer_control_addr)
        self._announce(new_session_id, Role.VIEWER, PortType.VIDEO, new_viewer_video_addr)
        self._announce(new_session_id, Role.VIEWER, PortType.CONTROL, new_viewer_control_addr)

        # New session should be ready and overwrite mappings
        self.assertIn(new_session_id, self.relay.sessions)
        self.assertEqual(len(self.relay.sessions), 1)

        # Forwarding should now target the new viewer
        self.mock_sock.reset_mock()
        self.relay.forward_packet(b"data", self.streamer_video_addr)
        self.mock_sock.sendto.assert_called_once_with(b"data", new_viewer_video_addr)

    def test_concurrent_access_thread_safety(self) -> None:
        """Test thread safety of concurrent operations."""
        self.mock_store.exists.return_value = True

        results = []
        errors = []

        def register_peers_worker(session_suffix: str) -> None:
            try:
                session_id = f"session_{session_suffix}"
                # Register complete session
                self._announce(session_id, Role.STREAMER, PortType.VIDEO, (f"10.0.0.{session_suffix}", 5000))
                self._announce(session_id, Role.STREAMER, PortType.CONTROL, (f"10.0.0.{session_suffix}", 5001))
                self._announce(session_id, Role.VIEWER, PortType.VIDEO, (f"10.0.1.{session_suffix}", 6000))
                self._announce(session_id, Role.VIEWER, PortType.CONTROL, (f"10.0.1.{session_suffix}", 6001))
                session_ready = self.relay.sessions[session_id].is_ready()
                results.append((session_id, session_ready))
            except Exception as e:
                errors.append(e)

        def cleanup_worker() -> None:
            try:
                for _ in range(10):
                    self.relay.cleanup_expired_mappings()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=register_peers_worker, args=(str(i),))
            threads.append(t)
            t.start()

        cleanup_thread = threading.Thread(target=cleanup_worker)
        threads.append(cleanup_thread)
        cleanup_thread.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Verify all sessions became ready
        self.assertEqual(len(results), 5)
        for session_id, is_ready in results:
            self.assertTrue(is_ready, f"Session {session_id} should be ready")

    def test_get_session_peers_nonexistent_session(self) -> None:
        peers = self.relay.get_session_peers("nonexistent")
        self.assertEqual(peers, {})

    def test_partial_session_ready_check(self) -> None:
        """Test that session is not ready until both roles have all port types."""
        self.mock_store.exists.return_value = True

        # Only streamer with both ports
        self._announce(self.session_id, Role.STREAMER, PortType.VIDEO, self.streamer_video_addr)
        self._announce(self.session_id, Role.STREAMER, PortType.CONTROL, self.streamer_control_addr)
        self.assertFalse(self.relay.sessions[self.session_id].is_ready())

        # Add viewer with only one port
        self._announce(self.session_id, Role.VIEWER, PortType.VIDEO, self.viewer_video_addr)
        self.assertFalse(self.relay.sessions[self.session_id].is_ready())

        # Session should only be ready when viewer has both ports
        self._announce(self.session_id, Role.VIEWER, PortType.CONTROL, self.viewer_control_addr)
        self.assertTrue(self.relay.sessions[self.session_id].is_ready())

    def _setup_complete_session(self) -> None:
        """Helper to set up a complete session with both roles and port types."""
        self._announce(self.session_id, Role.STREAMER, PortType.VIDEO, self.streamer_video_addr)
        self._announce(self.session_id, Role.STREAMER, PortType.CONTROL, self.streamer_control_addr)
        self._announce(self.session_id, Role.VIEWER, PortType.VIDEO, self.viewer_video_addr)
        self._announce(self.session_id, Role.VIEWER, PortType.CONTROL, self.viewer_control_addr)

    def test_cleanup_with_partial_session_expiry(self) -> None:
        """
        Test cleanup when only some mappings of a session expire.
        """
        self.mock_store.exists.return_value = True

        initial_time = 1_600_000_000.0
        with patch('time.time', return_value=initial_time):
            self._setup_complete_session()

        # Update only video mapping timestamp (simulate activity)
        mid_time = initial_time + 1.0
        with patch('time.time', return_value=mid_time):
            # forward updates timestamp for streamer_video_addr
            self.mock_sock.reset_mock()
            self.relay.forward_packet(b"data", self.streamer_video_addr)
            self.mock_sock.sendto.assert_called_once()

        # Fast forward past timeout: control mappings should expire (they were not updated),
        # video mapping may still be considered active if mid_time is recent enough
        expired_time = initial_time + self.timeout + 1
        with patch('time.time', return_value=expired_time):
            with patch('logging.info') as mock_log:
                self.relay.cleanup_expired_mappings()
                self.assertGreater(mock_log.call_count, 0)

        # Session should still exist because at least one mapping (video) remained active
        peers = self.relay.get_session_peers(self.session_id)
        self.assertEqual(len(peers), 2)

        # Video mapping should still work
        self.mock_sock.reset_mock()
        self.relay.forward_packet(b"data", self.streamer_video_addr)
        self.mock_sock.sendto.assert_called_once()

        # Control mapping should be gone
        self.mock_sock.reset_mock()
        self.relay.forward_packet(b"data", self.streamer_control_addr)
        self.mock_sock.sendto.assert_not_called()

    def test_cleanup_expired_mappings_no_sessions_affected(self) -> None:
        """
        Test cleanup when mappings exist but no sessions are found for them.
        """
        self.mock_store.exists.return_value = True

        fake_addr = ("192.168.1.99", 9999)
        target_addr = ("192.168.1.100", 9900)

        old_time = time.time() - self.timeout - 1
        with self.relay.mapping_lock:
            self.relay.mappings[fake_addr] = (target_addr, old_time)

        with patch('logging.info') as mock_log:
            self.relay.cleanup_expired_mappings()
            mock_log.assert_called()

        with self.relay.mapping_lock:
            self.assertNotIn(fake_addr, self.relay.mappings)

    def test_cleanup_orphaned_sessions_with_ready_sessions_mixed(self) -> None:
        """Test cleanup with mix of orphaned and ready sessions."""
        self.mock_store.exists.return_value = True

        # Create one complete session
        self._setup_complete_session()

        # Create an orphaned session (incomplete) with old last_announcement_at
        orphaned_session_id = "orphaned_session"
        old_time = time.time() - self.timeout - 1

        # register while patching time to old_time
        with patch('time.time', return_value=old_time):
            self._announce(orphaned_session_id, Role.STREAMER, PortType.VIDEO, ("10.0.0.1", 5000))

        # Both sessions should exist initially
        complete_peers = self.relay.get_session_peers(self.session_id)
        orphaned_peers = self.relay.get_session_peers(orphaned_session_id)
        self.assertGreater(len(complete_peers), 0)
        self.assertGreater(len(orphaned_peers), 0)

        # Cleanup should remove only orphaned session
        with patch('logging.info') as mock_log:
            self.relay.cleanup_expired_mappings()
            mock_log.assert_called()

        complete_peers_after = self.relay.get_session_peers(self.session_id)
        orphaned_peers_after = self.relay.get_session_peers(orphaned_session_id)

        self.assertGreater(len(complete_peers_after), 0)
        self.assertEqual(len(orphaned_peers_after), 0)


if __name__ == "__main__":
    unittest.main()
