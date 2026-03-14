import os
import socket
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from v3xctrl_control.message import (
    ConnectionTest,
    ConnectionTestAck,
    Message,
    PeerAnnouncement,
)
from v3xctrl_relay.custom_types import PortType, Role, Session
from v3xctrl_relay.ForwardTarget import TcpTarget
from v3xctrl_relay.PacketRelay import Mapping
from v3xctrl_relay.RelayServer import RelayServer
from v3xctrl_tcp import Transport


class TestRelayServerUnitTests(unittest.TestCase):
    """Unit tests targeting specific uncovered lines and error paths."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        # command_socket_path is now derived from port automatically

        # Initialize test database
        self._init_test_db()

        self.server_ip = "127.0.0.1"
        self.server_port = 12345

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _init_test_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS allowed_sessions (
                    id TEXT PRIMARY KEY,
                    spectator_id TEXT NOT NULL UNIQUE,
                    discord_user_id TEXT NOT NULL UNIQUE,
                    discord_username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute(
                "INSERT INTO allowed_sessions (id, spectator_id, discord_user_id, discord_username) VALUES (?, ?, ?, ?)",
                ("test_session_1", "test_spectator_1", "user123", "testuser")
            )
            conn.commit()

    @patch('socket.socket')
    def test_shutdown_socket_error_handling(self, mock_socket_class):
        """Test error handling in shutdown method - lines 64, 66-68, 78-79, 85-87"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        # Make socket.close() raise exceptions
        mock_udp_socket.close.side_effect = Exception("UDP socket close error")
        mock_command_socket.close.side_effect = Exception("Command socket close error")

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Test shutdown with socket errors - should not raise exceptions
        with patch('logging.warning') as mock_warning:
            server.shutdown()

            # Verify warnings were logged for both socket errors
            self.assertGreaterEqual(mock_warning.call_count, 1)

    @patch('socket.socket')
    def test_shutdown_without_command_socket(self, mock_socket_class):
        """Test shutdown when command socket doesn't exist - line 82->84"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        # Create server but remove command_sock attribute to test hasattr check
        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Remove command_sock to test the hasattr branch
        del server.command_sock

        # Should not raise exception
        server.shutdown()

    @patch('socket.socket')
    def test_handle_commands_accept_error(self, mock_socket_class):
        """Test _handle_commands OSError handling - line 95"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        # Make accept() raise OSError
        mock_command_socket.accept.side_effect = OSError("Accept error")

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Mock running to be False to exit loop
        server.running.clear()

        # Call _handle_commands - should not raise exception
        server._handle_commands()

    @patch('socket.socket')
    def test_handle_commands_generic_exception(self, mock_socket_class):
        """Test _handle_commands generic exception handling - lines 103-115"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        # Make accept() raise a generic exception (not OSError)
        mock_command_socket.accept.side_effect = Exception("Generic error")

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Set running to False after one iteration
        server.running.set()

        with patch('logging.error') as mock_error:
            # Call _handle_commands with a counter to limit iterations
            _original_is_set = server.running.is_set
            call_count = 0

            def limited_is_set():
                nonlocal call_count
                call_count += 1
                return call_count == 1  # Only return True once

            server.running.is_set = limited_is_set
            server._handle_commands()

            # Verify error was logged
            mock_error.assert_called()

    @patch('socket.socket')
    def test_process_command_recv_error(self, mock_socket_class):
        """Test _process_command error handling - lines 103-115"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()
        mock_client_socket = Mock()

        # Make recv() raise an exception
        mock_client_socket.recv.side_effect = Exception("Recv error")

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        with patch('logging.error') as mock_error:
            server._process_command(mock_client_socket)

            # Verify error was logged
            mock_error.assert_called()
            # Verify socket was still closed
            mock_client_socket.close.assert_called_once()

    @patch('socket.socket')
    def test_get_session_stats_empty_sessions(self, mock_socket_class):
        """Test _get_session_stats with no sessions - lines 129-130"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Clear any existing sessions
        server.relay.sessions.clear()

        stats = server._get_session_stats()
        self.assertEqual(stats, {})

    @patch('socket.socket')
    def test_get_session_stats_no_mappings(self, mock_socket_class):
        """Test _get_session_stats with session but no mappings - lines 142->139, 144->143, 146->143"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Create a session with addresses but no mappings
        from v3xctrl_relay.custom_types import Session
        session = Session("test_session_1")
        session.addresses.add(("192.168.1.100", 54321))
        server.relay.sessions["test_session_1"] = session

        # Ensure no mappings exist for the address
        server.relay.mappings.clear()

        stats = server._get_session_stats()

        # Should have session but empty mappings
        self.assertIn("test_session_1", stats)
        self.assertEqual(len(stats["test_session_1"]["mappings"]), 0)

    @patch('socket.socket')
    def test_handle_peer_announcement_send_error_exception(self, mock_socket_class):
        """Test _handle_peer_announcement error message sending failure - lines 188-189"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        # Make sendto raise an exception
        mock_udp_socket.sendto.side_effect = Exception("Send error")

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Create mock peer announcement for unknown session
        peer_announcement = Mock(spec=PeerAnnouncement)
        peer_announcement.get_id.return_value = "unknown_session"
        peer_announcement.get_role.return_value = Role.STREAMER.value
        peer_announcement.get_port_type.return_value = PortType.VIDEO.value

        client_addr = ("192.168.1.100", 54321)

        with patch('v3xctrl_relay.PacketRelay.logger') as mock_logger:
            server._handle_peer_announcement(peer_announcement, client_addr)

            # Verify error was logged for the send failure
            mock_logger.error.assert_called()

    @patch('socket.socket')
    def test_handle_slow_packet_message_parse_exception(self, mock_socket_class):
        """Test _handle_slow_packet Message.from_bytes exception for PeerAnnouncement prefix."""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Test peer announcement data that causes Message.from_bytes to fail
        peer_announcement_data = b'\x83\xa1t\xb0PeerAnnouncement' + b'invalid_data'
        client_addr = ("192.168.1.100", 54321)

        # Mock Message.from_bytes to raise an exception
        with patch('v3xctrl_relay.RelayServer.Message') as mock_message_class:
            mock_message_class.from_bytes.side_effect = Exception("Parse error")

            # Should not raise exception, just return early
            server._handle_slow_packet(peer_announcement_data, client_addr)

    @patch('socket.socket')
    def test_handle_slow_packet_general_exception(self, mock_socket_class):
        """Test _handle_slow_packet general exception handling."""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Mock update_spectator_heartbeat to raise an exception
        with patch.object(server.relay, 'update_spectator_heartbeat', side_effect=Exception("Heartbeat error")):
            regular_data = b'regular_packet_data'
            client_addr = ("192.168.1.100", 54321)

            with patch('logging.error') as mock_error:
                server._handle_slow_packet(regular_data, client_addr)

                # Verify error was logged
                mock_error.assert_called()

    @patch('socket.socket')
    def test_handle_slow_packet_non_peer_announcement_isinstance_false(self, mock_socket_class):
        """Test _handle_slow_packet when Message.from_bytes returns non-PeerAnnouncement."""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )

        # Test peer announcement data that parses but isn't a PeerAnnouncement
        peer_announcement_data = b'\x83\xa1t\xb0PeerAnnouncement' + b'data'
        client_addr = ("192.168.1.100", 54321)

        # Mock Message.from_bytes to return a different message type
        with patch('v3xctrl_relay.RelayServer.Message') as mock_message_class:
            mock_other_msg = Mock()  # Not a PeerAnnouncement
            mock_message_class.from_bytes.return_value = mock_other_msg

            # Falls through isinstance check, then calls update_spectator_heartbeat
            with patch.object(server.relay, 'update_spectator_heartbeat') as mock_heartbeat:
                server._handle_slow_packet(peer_announcement_data, client_addr)

                mock_heartbeat.assert_called_once_with(client_addr)

    # -- Connection test (relay test button) --

    def _create_server_with_mock_socket(self, mock_socket_class):
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = RelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
        )
        return server, mock_udp_socket

    def _parse_connection_test_ack(self, mock_udp_socket) -> ConnectionTestAck:
        ack_bytes = mock_udp_socket.sendto.call_args[0][0]
        msg = Message.from_bytes(ack_bytes)
        self.assertIsInstance(msg, ConnectionTestAck)
        return msg

    @patch('socket.socket')
    def test_connection_test_valid_session_id(self, mock_socket_class):
        """ConnectionTest with valid session ID returns ack with valid=True."""
        server, mock_udp_socket = self._create_server_with_mock_socket(mock_socket_class)

        data = ConnectionTest(i="test_session_1", s=False).to_bytes()
        addr = ("192.168.1.100", 54321)

        server._handle_connection_test(data, addr)

        ack = self._parse_connection_test_ack(mock_udp_socket)
        self.assertTrue(ack.valid)
        self.assertEqual(mock_udp_socket.sendto.call_args[0][1], addr)

    @patch('socket.socket')
    def test_connection_test_invalid_session_id(self, mock_socket_class):
        """ConnectionTest with invalid session ID returns ack with valid=False."""
        server, mock_udp_socket = self._create_server_with_mock_socket(mock_socket_class)

        data = ConnectionTest(i="nonexistent_session", s=False).to_bytes()
        addr = ("192.168.1.100", 54321)

        server._handle_connection_test(data, addr)

        ack = self._parse_connection_test_ack(mock_udp_socket)
        self.assertFalse(ack.valid)

    @patch('socket.socket')
    def test_connection_test_valid_spectator_id(self, mock_socket_class):
        """ConnectionTest with valid spectator ID returns ack with valid=True."""
        server, mock_udp_socket = self._create_server_with_mock_socket(mock_socket_class)

        data = ConnectionTest(i="test_spectator_1", s=True).to_bytes()
        addr = ("192.168.1.100", 54321)

        server._handle_connection_test(data, addr)

        ack = self._parse_connection_test_ack(mock_udp_socket)
        self.assertTrue(ack.valid)

    @patch('socket.socket')
    def test_connection_test_invalid_spectator_id(self, mock_socket_class):
        """ConnectionTest with invalid spectator ID returns ack with valid=False."""
        server, mock_udp_socket = self._create_server_with_mock_socket(mock_socket_class)

        data = ConnectionTest(i="nonexistent_spectator", s=True).to_bytes()
        addr = ("192.168.1.100", 54321)

        server._handle_connection_test(data, addr)

        ack = self._parse_connection_test_ack(mock_udp_socket)
        self.assertFalse(ack.valid)

    # -- Spectator stats --

    def _setup_session_with_spectator(self, server, transport=Transport.UDP):
        """Set up a ready session with one spectator. Returns spectator addresses."""
        session = Session("test_session_1")

        # Register streamer and viewer to make session ready
        streamer_video_addr = ("10.0.0.1", 5000)
        streamer_control_addr = ("10.0.0.1", 5001)
        viewer_video_addr = ("10.0.0.2", 6000)
        viewer_control_addr = ("10.0.0.2", 6001)

        session.register(Role.STREAMER, PortType.VIDEO, streamer_video_addr)
        session.register(Role.STREAMER, PortType.CONTROL, streamer_control_addr)
        session.register(Role.VIEWER, PortType.VIDEO, viewer_video_addr)
        session.register(Role.VIEWER, PortType.CONTROL, viewer_control_addr)

        # Add mappings for streamer
        now = time.time()
        server.relay.mappings[streamer_video_addr] = Mapping({viewer_video_addr}, now)
        server.relay.mappings[viewer_video_addr] = Mapping({streamer_video_addr}, now)
        server.relay.mappings[streamer_control_addr] = Mapping({viewer_control_addr}, now)
        server.relay.mappings[viewer_control_addr] = Mapping({streamer_control_addr}, now)

        # Register spectator
        spectator_video_addr = ("10.0.0.3", 7000)
        spectator_control_addr = ("10.0.0.3", 7001)

        session.register(Role.SPECTATOR, PortType.VIDEO, spectator_video_addr, transport)
        session.register(Role.SPECTATOR, PortType.CONTROL, spectator_control_addr, transport)

        server.relay.sessions["test_session_1"] = session

        return spectator_video_addr, spectator_control_addr

    @patch('socket.socket')
    def test_spectator_stats_include_transport_udp(self, mock_socket_class):
        """UDP spectator stats include transport=UDP."""
        server, _ = self._create_server_with_mock_socket(mock_socket_class)
        self._setup_session_with_spectator(server, Transport.UDP)

        stats = server._get_session_stats()
        spectators = stats["test_session_1"]["spectators"]

        self.assertEqual(len(spectators), 2)
        for entry in spectators:
            self.assertEqual(entry["transport"], "UDP")

    @patch('socket.socket')
    def test_spectator_stats_include_transport_tcp(self, mock_socket_class):
        """TCP spectator stats include transport=TCP."""
        server, _ = self._create_server_with_mock_socket(mock_socket_class)
        spectator_video_addr, spectator_control_addr = self._setup_session_with_spectator(
            server, Transport.TCP
        )

        # Add alive TCP targets for spectator addresses
        target_video = TcpTarget(Mock())
        target_control = TcpTarget(Mock())
        server.relay.tcp_targets[spectator_video_addr] = target_video
        server.relay.tcp_targets[spectator_control_addr] = target_control

        stats = server._get_session_stats()
        spectators = stats["test_session_1"]["spectators"]

        self.assertEqual(len(spectators), 2)
        for entry in spectators:
            self.assertEqual(entry["transport"], "TCP")

    @patch('socket.socket')
    def test_tcp_spectator_timeout_stays_full_with_active_connection(self, mock_socket_class):
        """TCP spectator with active connection shows full SPECTATOR_TIMEOUT."""
        server, _ = self._create_server_with_mock_socket(mock_socket_class)
        spectator_video_addr, spectator_control_addr = self._setup_session_with_spectator(
            server, Transport.TCP
        )

        # Add alive TCP targets
        target = TcpTarget(Mock())
        server.relay.tcp_targets[spectator_video_addr] = target

        # Artificially age the last_announcement_at to simulate time passing
        session = server.relay.sessions["test_session_1"]
        session.spectators[0].last_announcement_at = time.time() - 25

        stats = server._get_session_stats()
        spectators = stats["test_session_1"]["spectators"]

        # Should show full SPECTATOR_TIMEOUT, not the decayed value
        for entry in spectators:
            self.assertEqual(entry["timeout_in_sec"], server.relay.SPECTATOR_TIMEOUT)

    @patch('socket.socket')
    def test_udp_spectator_timeout_decays_normally(self, mock_socket_class):
        """UDP spectator timeout decays based on last_announcement_at."""
        server, _ = self._create_server_with_mock_socket(mock_socket_class)
        self._setup_session_with_spectator(server, Transport.UDP)

        # Age the last_announcement_at by 10 seconds
        session = server.relay.sessions["test_session_1"]
        session.spectators[0].last_announcement_at = time.time() - 10

        stats = server._get_session_stats()
        spectators = stats["test_session_1"]["spectators"]

        # Should show decayed timeout (~20 seconds remaining)
        for entry in spectators:
            self.assertLess(entry["timeout_in_sec"], server.relay.SPECTATOR_TIMEOUT)
            self.assertGreater(entry["timeout_in_sec"], 0)

    @patch('socket.socket')
    def test_tcp_spectator_timeout_decays_when_connection_dead(self, mock_socket_class):
        """TCP spectator with dead connection shows decayed timeout."""
        server, _ = self._create_server_with_mock_socket(mock_socket_class)
        spectator_video_addr, spectator_control_addr = self._setup_session_with_spectator(
            server, Transport.TCP
        )

        # Add dead TCP targets
        target = TcpTarget(Mock())
        target.close()
        server.relay.tcp_targets[spectator_video_addr] = target

        target2 = TcpTarget(Mock())
        target2.close()
        server.relay.tcp_targets[spectator_control_addr] = target2

        # Age the last_announcement_at
        session = server.relay.sessions["test_session_1"]
        session.spectators[0].last_announcement_at = time.time() - 10

        stats = server._get_session_stats()
        spectators = stats["test_session_1"]["spectators"]

        # Should show decayed timeout since TCP connections are dead
        for entry in spectators:
            self.assertLess(entry["timeout_in_sec"], server.relay.SPECTATOR_TIMEOUT)


if __name__ == '__main__':
    unittest.main()
