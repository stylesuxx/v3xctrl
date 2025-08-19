import unittest
from unittest.mock import MagicMock, patch, call
import time
import threading
import socket

from src.v3xctrl_udp_relay.UDPRelayServer import UDPRelayServer, Role, PortType, Session, PeerEntry
from src.v3xctrl_control.message import PeerAnnouncement, PeerInfo, Error


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

        # Patch ThreadPoolExecutor
        self.executor_patcher = patch("src.v3xctrl_udp_relay.UDPRelayServer.ThreadPoolExecutor")
        self.mock_executor_cls = self.executor_patcher.start()
        self.mock_executor = MagicMock()
        self.mock_executor_cls.return_value = self.mock_executor

        self.server = UDPRelayServer("127.0.0.1", 9999, "fake.db")

    def tearDown(self):
        self.store_patcher.stop()
        self.socket_patcher.stop()
        self.executor_patcher.stop()

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
            sess.roles[Role.STREAMER][pt] = PeerEntry(("1.1.1.1", 1111))
            sess.roles[Role.STREAMER][pt].ts = now - 99999
        self.server.sessions[sid] = sess

        self.server.running.clear()  # Run loop once
        with patch("time.time", return_value=now):
            # Manually invoke one loop iteration
            self.server.running.set()
            with patch("time.sleep", side_effect=lambda _: self.server.running.clear()):
                self.server._clean_expired_entries()

        self.assertNotIn(sid, self.server.sessions)
        self.assertFalse(self.server.relay_map)

    def test_clean_expired_entries_partial_expiry(self):
        """Test partial role expiry - both port types expired for one role"""
        now = time.time()
        sid = "sess"
        # Both port types expired for STREAMER role
        self.server.relay_map = {
            ("1.1.1.1", 1111): {
                "session": sid,
                "role": Role.STREAMER,
                "port_type": PortType.VIDEO,
                "ts": now - 99999,  # Expired
            },
            ("1.1.1.1", 1112): {
                "session": sid,
                "role": Role.STREAMER,
                "port_type": PortType.CONTROL,
                "ts": now - 99999,  # Expired
            },
            ("2.2.2.2", 2222): {
                "session": sid,
                "role": Role.VIEWER,
                "port_type": PortType.VIDEO,
                "ts": now - 1,  # Not expired
            },
        }
        sess = Session()
        # STREAMER peer entries are expired
        sess.roles[Role.STREAMER][PortType.VIDEO] = PeerEntry(("1.1.1.1", 1111))
        sess.roles[Role.STREAMER][PortType.VIDEO].ts = now - 99999
        sess.roles[Role.STREAMER][PortType.CONTROL] = PeerEntry(("1.1.1.1", 1112))
        sess.roles[Role.STREAMER][PortType.CONTROL].ts = now - 99999
        # VIEWER peer entry is not expired
        sess.roles[Role.VIEWER][PortType.VIDEO] = PeerEntry(("2.2.2.2", 2222))
        sess.roles[Role.VIEWER][PortType.VIDEO].ts = now - 1
        self.server.sessions[sid] = sess

        self.server.running.clear()
        with patch("time.time", return_value=now):
            self.server.running.set()
            with patch("time.sleep", side_effect=lambda _: self.server.running.clear()):
                self.server._clean_expired_entries()

        # Session should still exist because VIEWER has active mapping
        self.assertIn(sid, self.server.sessions)
        # STREAMER mappings should be removed
        self.assertNotIn(("1.1.1.1", 1111), self.server.relay_map)
        self.assertNotIn(("1.1.1.1", 1112), self.server.relay_map)
        # VIEWER mapping should remain
        self.assertIn(("2.2.2.2", 2222), self.server.relay_map)
        # STREAMER role should be cleared
        self.assertEqual(self.server.sessions[sid].roles[Role.STREAMER], {})
        # VIEWER role should remain
        self.assertIn(PortType.VIDEO, self.server.sessions[sid].roles[Role.VIEWER])

    def test_clean_expired_entries_no_cleanup_partial_expiry(self):
        """Test that cleanup doesn't happen when only some port types are expired"""
        now = time.time()
        sid = "sess"
        self.server.relay_map = {
            ("1.1.1.1", 1111): {
                "session": sid,
                "role": Role.STREAMER,
                "port_type": PortType.VIDEO,
                "ts": now - 99999,  # Expired
            },
            ("1.1.1.1", 1112): {
                "session": sid,
                "role": Role.STREAMER,
                "port_type": PortType.CONTROL,
                "ts": now - 1,  # Not expired
            },
        }
        sess = Session()
        sess.roles[Role.STREAMER][PortType.VIDEO] = PeerEntry(("1.1.1.1", 1111))
        sess.roles[Role.STREAMER][PortType.VIDEO].ts = now - 99999
        sess.roles[Role.STREAMER][PortType.CONTROL] = PeerEntry(("1.1.1.1", 1112))
        sess.roles[Role.STREAMER][PortType.CONTROL].ts = now - 1
        self.server.sessions[sid] = sess

        self.server.running.clear()
        with patch("time.time", return_value=now):
            self.server.running.set()
            with patch("time.sleep", side_effect=lambda _: self.server.running.clear()):
                self.server._clean_expired_entries()

        # Session should still exist and mappings should remain because not all ports expired
        self.assertIn(sid, self.server.sessions)
        # Both mappings should still exist (cleanup only happens when ALL port types are expired)
        self.assertIn(("1.1.1.1", 1111), self.server.relay_map)
        self.assertIn(("1.1.1.1", 1112), self.server.relay_map)

    def test_clean_expired_entries_session_with_active_mapping(self):
        """Test session is not expired if it has active relay mappings"""
        now = time.time()
        sid = "sess"
        self.server.relay_map = {
            ("1.1.1.1", 1111): {
                "session": sid,
                "role": Role.STREAMER,
                "port_type": PortType.VIDEO,
                "ts": now - 1,  # Active mapping
            },
        }
        sess = Session()
        # Old peer entries but active mapping should keep session alive
        sess.roles[Role.STREAMER][PortType.VIDEO] = PeerEntry(("1.1.1.1", 1111))
        sess.roles[Role.STREAMER][PortType.VIDEO].ts = now - 99999
        self.server.sessions[sid] = sess

        self.server.running.clear()
        with patch("time.time", return_value=now):
            self.server.running.set()
            with patch("time.sleep", side_effect=lambda _: self.server.running.clear()):
                self.server._clean_expired_entries()

        # Session should still exist due to active mapping
        self.assertIn(sid, self.server.sessions)

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
        # Should send error message
        self.mock_sock.sendto.assert_called()
        args = self.mock_sock.sendto.call_args[0]
        self.assertEqual(args[1], ("1.1.1.1", 1111))

    def test_handle_peer_announcement_unknown_session_sendto_fails(self):
        """Test error handling when sendto fails for unknown session"""
        self.mock_store.exists.return_value = False
        self.mock_sock.sendto.side_effect = Exception("Network error")

        msg = MagicMock()
        msg.get_id.return_value = "sess"
        msg.get_role.return_value = Role.STREAMER.value
        msg.get_port_type.return_value = PortType.VIDEO.value

        with patch('logging.error') as mock_log:
            self.server._handle_peer_announcement(msg, ("1.1.1.1", 1111))
            mock_log.assert_called()

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
        # Should send PeerInfo to all peers
        self.assertEqual(self.mock_sock.sendto.call_count, 4)  # 2 roles x 2 port types

    def test_handle_peer_announcement_peer_info_send_fails(self):
        """Test error handling when PeerInfo sendto fails"""
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

        self.mock_sock.sendto.side_effect = Exception("Send failed")

        with patch('logging.error') as mock_log:
            self.server._handle_peer_announcement(msg, ("1.1.1.1", 1111))
            mock_log.assert_called()

    def test_handle_peer_announcement_existing_mapping_purge(self):
        """Test that existing mappings are purged when new mapping is created"""
        self.mock_store.exists.return_value = True
        sid = "sess"

        # Setup existing mappings
        self.server.relay_map = {
            ("3.3.3.3", 3333): {
                "session": sid,
                "role": Role.STREAMER,
                "port_type": PortType.VIDEO,
                "ts": time.time(),
            }
        }

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

        # Old mapping should be purged
        self.assertNotIn(("3.3.3.3", 3333), self.server.relay_map)
        # New mappings should exist
        self.assertIn(("1.1.1.1", 1111), self.server.relay_map)

    def test_handle_peer_announcement_new_peer_logging(self):
        """Test logging for new peer registration"""
        self.mock_store.exists.return_value = True
        msg = MagicMock()
        msg.get_id.return_value = "sess"
        msg.get_role.return_value = Role.STREAMER.value
        msg.get_port_type.return_value = PortType.VIDEO.value

        with patch('logging.info') as mock_log:
            self.server._handle_peer_announcement(msg, ("1.1.1.1", 1111))
            # Should log new peer registration
            mock_log.assert_called()

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

    def test_forward_packet_no_mapping(self):
        """Test forward packet when no mapping exists"""
        self.server._forward_packet(b"data", ("1.1.1.1", 1111))
        self.mock_sock.sendto.assert_not_called()

    def test_handle_packet_with_peer_announcement(self):
        msg = MagicMock(spec=PeerAnnouncement)
        with patch("src.v3xctrl_udp_relay.UDPRelayServer.Message.from_bytes", return_value=msg):
            data = b"\x83\xa1t\xb0PeerAnnouncement"
            self.server._handle_packet(data, ("1.1.1.1", 1111))

    def test_handle_packet_malformed_announcement(self):
        with patch("src.v3xctrl_udp_relay.UDPRelayServer.Message.from_bytes", side_effect=Exception("bad")):
            data = b"\x83\xa1t\xb0PeerAnnouncement"
            with patch('logging.debug') as mock_log:
                self.server._handle_packet(data, ("1.1.1.1", 1111))
                mock_log.assert_called_with("Malformed peer announcement")

    def test_handle_packet_non_announcement_message(self):
        """Test handling non-PeerAnnouncement message that starts with announcement prefix"""
        msg = MagicMock()  # Not a PeerAnnouncement
        with patch("src.v3xctrl_udp_relay.UDPRelayServer.Message.from_bytes", return_value=msg):
            data = b"\x83\xa1t\xb0PeerAnnouncement"
            self.server._handle_packet(data, ("1.1.1.1", 1111))
            # Should return without processing

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

    def test_handle_packet_exception_handling(self):
        """Test exception handling in _handle_packet"""
        with patch.object(self.server, '_forward_packet', side_effect=Exception("Forward error")):
            addr = ("1.1.1.1", 1111)
            self.server.relay_map[addr] = {"target": ("2.2.2.2", 2222)}

            with patch('logging.error') as mock_log:
                self.server._handle_packet(b"payload", addr)
                mock_log.assert_called()

    @patch('threading.Thread')
    @patch('logging.info')
    def test_run_method_startup(self, mock_log, mock_thread):
        """Test run method startup and cleanup thread creation"""
        # Mock recvfrom to raise OSError immediately to exit loop
        self.mock_sock.recvfrom.side_effect = OSError("Socket closed")
        self.server.running.clear()  # Stop immediately

        self.server.run()

        # Should log startup message
        mock_log.assert_called_with("UDP Relay server listening on 127.0.0.1:9999")
        # Should start cleanup thread
        mock_thread.assert_called()

    @patch('threading.Thread')
    def test_run_method_packet_handling(self, mock_thread):
        """Test run method packet handling"""
        # Mock recvfrom to return data once then raise OSError
        self.mock_sock.recvfrom.side_effect = [
            (b"test_data", ("1.1.1.1", 1111)),
            OSError("Socket closed")
        ]
        # Keep running set so loop executes
        self.server.running.set()

        # After first packet, clear running to exit loop
        def clear_after_submit(*args):
            self.server.running.clear()
            return MagicMock()

        self.mock_executor.submit.side_effect = clear_after_submit

        self.server.run()

        # Should submit packet handling to executor
        self.mock_executor.submit.assert_called_once()

    @patch('threading.Thread')
    @patch('logging.error')
    def test_run_method_socket_error_while_running(self, mock_log, mock_thread):
        """Test run method handling socket error while running"""
        self.server.running.set()  # Keep running

        # First call raises OSError, second call clears running and raises OSError to exit
        call_count = 0
        def side_effect(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First error while still running
                raise OSError("Network error")
            else:
                # Second call - clear running to exit loop
                self.server.running.clear()
                raise OSError("Socket closed")

        self.mock_sock.recvfrom.side_effect = side_effect

        self.server.run()

        # Should log socket error for the first OSError when running is still set
        mock_log.assert_called_with("Socket error")

    @patch('threading.Thread')
    @patch('logging.error')
    def test_run_method_unhandled_exception(self, mock_log, mock_thread):
        """Test run method handling unhandled exceptions"""
        def side_effect(*args):
            self.server.running.clear()
            raise ValueError("Unexpected error")

        self.mock_sock.recvfrom.side_effect = side_effect

        self.server.run()

        mock_log.assert_called()
        # Should log the unhandled error with exc_info
        self.assertIn("Unhandled error", mock_log.call_args[0][0])

    def test_shutdown_closes_socket(self):
        self.server.shutdown()
        self.mock_sock.close.assert_called()
        self.assertFalse(self.server.running.is_set())

    def test_shutdown_socket_close_error(self):
        """Test shutdown handles socket close errors gracefully"""
        self.mock_sock.close.side_effect = Exception("Close error")

        with patch('logging.warning') as mock_log:
            self.server.shutdown()
            mock_log.assert_called_with("Error closing socket: Close error")

    def test_peer_entry_initialization(self):
        """Test PeerEntry initialization"""
        addr = ("1.1.1.1", 1111)
        entry = PeerEntry(addr)
        self.assertEqual(entry.addr, addr)
        self.assertIsInstance(entry.ts, float)

    def test_session_register_new_peer(self):
        """Test Session.register with new peer"""
        session = Session()
        result = session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.assertTrue(result)  # Should be new peer

        # Register same port type again
        result = session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.2", 1112))
        self.assertFalse(result)  # Should not be new peer

    def test_session_is_ready(self):
        """Test Session.is_ready"""
        session = Session()
        self.assertFalse(session.is_ready(Role.STREAMER))

        session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))
        self.assertFalse(session.is_ready(Role.STREAMER))

        session.register(Role.STREAMER, PortType.CONTROL, ("1.1.1.1", 1112))
        self.assertTrue(session.is_ready(Role.STREAMER))

    def test_session_get_peer_exists(self):
        """Test Session.get_peer when peer exists"""
        session = Session()
        session.register(Role.STREAMER, PortType.VIDEO, ("1.1.1.1", 1111))

        peer = session.get_peer(Role.STREAMER, PortType.VIDEO)
        self.assertIsNotNone(peer)
        self.assertEqual(peer.addr, ("1.1.1.1", 1111))

    def test_session_get_peer_not_exists(self):
        """Test Session.get_peer when peer doesn't exist"""
        session = Session()
        peer = session.get_peer(Role.STREAMER, PortType.VIDEO)
        self.assertIsNone(peer)

    @patch('socket.socket')
    def test_server_initialization_socket_setup(self, mock_socket):
        """Test server initialization sets up socket correctly"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock

        with patch("src.v3xctrl_udp_relay.UDPRelayServer.SessionStore"), \
             patch("src.v3xctrl_udp_relay.UDPRelayServer.ThreadPoolExecutor"):
            server = UDPRelayServer("127.0.0.1", 8888, "test.db")

        mock_socket.assert_called_with(socket.AF_INET, socket.SOCK_DGRAM)
        mock_sock.setsockopt.assert_called_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mock_sock.bind.assert_called_with(('0.0.0.0', 8888))


if __name__ == "__main__":
    unittest.main()
