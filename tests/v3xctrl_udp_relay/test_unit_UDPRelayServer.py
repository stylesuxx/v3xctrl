import os
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from v3xctrl_control.message import PeerAnnouncement
from v3xctrl_udp_relay.custom_types import Role, PortType
from v3xctrl_udp_relay.UDPRelayServer import UDPRelayServer


class TestUDPRelayServerUnitTests(unittest.TestCase):
    """Unit tests targeting specific uncovered lines and error paths."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.command_socket_path = os.path.join(self.temp_dir, 'test_command.sock')

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
                    discord_user_id TEXT NOT NULL UNIQUE,
                    discord_username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute(
                "INSERT INTO allowed_sessions (id, discord_user_id, discord_username) VALUES (?, ?, ?)",
                ("test_session_1", "user123", "testuser")
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

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
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
        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
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

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
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

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
        )

        # Set running to False after one iteration
        server.running.set()

        with patch('logging.error') as mock_error:
            # Call _handle_commands with a counter to limit iterations
            original_is_set = server.running.is_set
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

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
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

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
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

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
        )

        # Create a session with addresses but no mappings
        from v3xctrl_udp_relay.custom_types import Session
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

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
        )

        # Create mock peer announcement for unknown session
        peer_announcement = Mock(spec=PeerAnnouncement)
        peer_announcement.get_id.return_value = "unknown_session"
        peer_announcement.get_role.return_value = Role.STREAMER.value
        peer_announcement.get_port_type.return_value = PortType.VIDEO.value

        client_addr = ("192.168.1.100", 54321)

        with patch('logging.error') as mock_error:
            server._handle_peer_announcement(peer_announcement, client_addr)

            # Verify error was logged for the send failure
            mock_error.assert_called()

    @patch('socket.socket')
    def test_handle_packet_message_parse_exception(self, mock_socket_class):
        """Test _handle_packet Message.from_bytes exception - lines 228->234, 231-232"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
        )

        # Test peer announcement data that causes Message.from_bytes to fail
        peer_announcement_data = b'\x83\xa1t\xb0PeerAnnouncement' + b'invalid_data'
        client_addr = ("192.168.1.100", 54321)

        # Mock Message.from_bytes to raise an exception
        with patch('v3xctrl_udp_relay.UDPRelayServer.Message') as mock_message_class:
            mock_message_class.from_bytes.side_effect = Exception("Parse error")

            # Should not raise exception, just return early
            server._handle_packet(peer_announcement_data, client_addr)

    @patch('socket.socket')
    def test_handle_packet_general_exception(self, mock_socket_class):
        """Test _handle_packet general exception handling - lines 236-237"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
        )

        # Mock forward_packet to raise an exception
        with patch.object(server.relay, 'forward_packet', side_effect=Exception("Forward error")):
            regular_data = b'regular_packet_data'
            client_addr = ("192.168.1.100", 54321)

            with patch('logging.error') as mock_error:
                server._handle_packet(regular_data, client_addr)

                # Verify error was logged
                mock_error.assert_called()

    @patch('socket.socket')
    def test_handle_packet_non_peer_announcement_isinstance_false(self, mock_socket_class):
        """Test _handle_packet when Message.from_bytes returns non-PeerAnnouncement"""
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
        )

        # Test peer announcement data that parses but isn't a PeerAnnouncement
        peer_announcement_data = b'\x83\xa1t\xb0PeerAnnouncement' + b'data'
        client_addr = ("192.168.1.100", 54321)

        # Mock Message.from_bytes to return a different message type
        with patch('v3xctrl_udp_relay.UDPRelayServer.Message') as mock_message_class:
            mock_other_msg = Mock()  # Not a PeerAnnouncement
            mock_message_class.from_bytes.return_value = mock_other_msg

            # Should call forward_packet instead of _handle_peer_announcement
            with patch.object(server.relay, 'forward_packet') as mock_forward:
                server._handle_packet(peer_announcement_data, client_addr)

                # Should forward the packet since it's not a PeerAnnouncement
                mock_forward.assert_called_once_with(peer_announcement_data, client_addr)

if __name__ == '__main__':
    unittest.main()
