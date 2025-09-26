import json
import os
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from v3xctrl_control.message import PeerAnnouncement
from v3xctrl_udp_relay.custom_types import Role, PortType
from v3xctrl_udp_relay.UDPRelayServer import UDPRelayServer
from v3xctrl_udp_relay.custom_types import Session


class TestUDPRelayServerIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.command_socket_path = os.path.join(self.temp_dir, 'test_command.sock')

        # Initialize test database
        self._init_test_db()

        # Create server config
        self.server_ip = "127.0.0.1"
        self.server_port = 12345

    def tearDown(self):
        # Clean up temporary files
        if hasattr(self, 'server'):
            try:
                self.server.shutdown()
                if hasattr(self.server, 'join'):
                    self.server.join(timeout=0.1)
            except:
                pass

        # Clean up temp directory and all files
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _build_announce(
        self,
        sid: str,
        role: Role,
        port_type: PortType
    ):
        msg = PeerAnnouncement(role.value, sid, port_type.value)
        return msg

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
            # Insert test sessions
            cur.execute(
                "INSERT INTO allowed_sessions (id, discord_user_id, discord_username) VALUES (?, ?, ?)",
                ("test_session_1", "user123", "testuser")
            )
            cur.execute(
                "INSERT INTO allowed_sessions (id, discord_user_id, discord_username) VALUES (?, ?, ?)",
                ("test_session_2", "user456", "testuser2")
            )
            conn.commit()

    @patch('socket.socket')
    def test_server_initialization_and_shutdown(self, mock_socket_class):
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        def socket_side_effect(family, sock_type):
            if family == socket.AF_INET and sock_type == socket.SOCK_DGRAM:
                return mock_udp_socket
            elif family == socket.AF_UNIX and sock_type == socket.SOCK_STREAM:
                return mock_command_socket
            return Mock()

        mock_socket_class.side_effect = socket_side_effect

        # Create server with custom command socket path
        server = UDPRelayServer(
            self.server_ip,
            self.server_port,
            self.db_path,
            self.command_socket_path
        )

        # Verify socket setup
        mock_udp_socket.setsockopt.assert_called_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mock_udp_socket.bind.assert_called_with(('0.0.0.0', self.server_port))
        mock_command_socket.bind.assert_called_with(self.command_socket_path)
        mock_command_socket.listen.assert_called_with(5)

        # Test shutdown
        server.shutdown()
        mock_udp_socket.close.assert_called_once()
        mock_command_socket.close.assert_called_once()

    @patch('socket.socket')
    def test_peer_announcement_handling_valid_session(self, mock_socket_class):
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

        peer_announcement = self._build_announce("test_session_1", Role.STREAMER, PortType.VIDEO)
        client_addr = ("192.168.1.100", 54321)

        server._handle_peer_announcement(peer_announcement, client_addr)

        self.assertIn("test_session_1", server.relay.sessions)
        server.shutdown()

    @patch('socket.socket')
    def test_peer_announcement_handling_invalid_session(self, mock_socket_class):
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

        peer_announcement = self._build_announce("unknown_session", Role.STREAMER, PortType.VIDEO)
        client_addr = ("192.168.1.100", 54321)

        server._handle_peer_announcement(peer_announcement, client_addr)

        mock_udp_socket.sendto.assert_called_once()
        _, sent_addr = mock_udp_socket.sendto.call_args[0]
        self.assertEqual(sent_addr, client_addr)
        server.shutdown()

    @patch('socket.socket')
    def test_session_ready_triggers_peer_info_exchange(self, mock_socket_class):
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

        streamer_video_announcement = self._build_announce("test_session_1", Role.STREAMER, PortType.VIDEO)
        streamer_control_announcement = self._build_announce("test_session_1", Role.STREAMER, PortType.CONTROL)
        viewer_video_announcement = self._build_announce("test_session_1", Role.VIEWER, PortType.VIDEO)
        viewer_control_announcement = self._build_announce("test_session_1", Role.VIEWER, PortType.CONTROL)

        server._handle_peer_announcement(streamer_video_announcement, ("192.168.1.100", 54321))
        server._handle_peer_announcement(streamer_control_announcement, ("192.168.1.100", 54322))
        server._handle_peer_announcement(viewer_video_announcement, ("192.168.1.101", 54321))

        mock_udp_socket.sendto.reset_mock()
        server._handle_peer_announcement(viewer_control_announcement, ("192.168.1.101", 54322))

        self.assertEqual(mock_udp_socket.sendto.call_count, 4)
        server.shutdown()

    @patch('socket.socket')
    def test_packet_forwarding(self, mock_socket_class):
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

        # Set up complete session - need both roles with both port types
        server.relay.register_peer(
            self._build_announce("test_session_1", Role.STREAMER, PortType.VIDEO),
            ("192.168.1.100", 54321)
        )
        server.relay.register_peer(
            self._build_announce("test_session_1", Role.STREAMER, PortType.CONTROL),
            ("192.168.1.100", 54322)
        )
        server.relay.register_peer(
            self._build_announce("test_session_1", Role.VIEWER, PortType.VIDEO),
            ("192.168.1.101", 54321)
        )
        server.relay.register_peer(
            self._build_announce("test_session_1", Role.VIEWER, PortType.CONTROL),
            ("192.168.1.101", 54322)
        )

        # Reset sendto calls from peer registration
        mock_udp_socket.sendto.reset_mock()

        # Test packet forwarding from streamer video port
        test_data = b"test_video_data"
        sender_addr = ("192.168.1.100", 54321)  # Streamer video port

        server._handle_packet(test_data, sender_addr)

        # Should forward to viewer video port
        mock_udp_socket.sendto.assert_called_once()
        forwarded_data, forwarded_addr = mock_udp_socket.sendto.call_args[0]
        self.assertEqual(forwarded_data, test_data)
        self.assertEqual(forwarded_addr, ("192.168.1.101", 54321))  # Viewer video port

        server.shutdown()

    @patch('socket.socket')
    def test_command_socket_stats(self, mock_socket_class):
        mock_udp_socket = Mock()
        mock_command_socket = Mock()
        mock_client_socket = Mock()

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

        # Set up complete session with all required ports
        server.relay.register_peer(
            self._build_announce("test_session_1", Role.STREAMER, PortType.VIDEO),
            ("192.168.1.100", 54321)
        )
        server.relay.register_peer(
            self._build_announce("test_session_1", Role.STREAMER, PortType.CONTROL),
            ("192.168.1.100", 54322)
        )
        server.relay.register_peer(
            self._build_announce("test_session_1", Role.VIEWER, PortType.VIDEO),
            ("192.168.1.101", 54321)
        )
        server.relay.register_peer(
            self._build_announce("test_session_1", Role.VIEWER, PortType.CONTROL),
            ("192.168.1.101", 54322)
        )

        # Test stats command
        mock_client_socket.recv.return_value = b"stats"

        server._process_command(mock_client_socket)

        # Verify response was sent
        mock_client_socket.send.assert_called_once()
        sent_data = mock_client_socket.send.call_args[0][0]

        # Parse and verify stats
        stats = json.loads(sent_data.decode('utf-8'))
        self.assertIn("test_session_1", stats)
        self.assertIn("mappings", stats["test_session_1"])
        # Should have mappings for addresses that are in relay.mappings
        self.assertGreater(len(stats["test_session_1"]["mappings"]), 0)

        # Verify socket was closed
        mock_client_socket.close.assert_called_once()

        server.shutdown()

    @patch('socket.socket')
    def test_command_socket_unknown_command(self, mock_socket_class):
        mock_udp_socket = Mock()
        mock_command_socket = Mock()
        mock_client_socket = Mock()

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

        # Test unknown command
        mock_client_socket.recv.return_value = b"unknown"

        server._process_command(mock_client_socket)

        # Verify error response
        mock_client_socket.send.assert_called_once_with(b"Unknown command")
        mock_client_socket.close.assert_called_once()

        server.shutdown()

    @patch('socket.socket')
    def test_invalid_role_or_port_type_ignored(self, mock_socket_class):
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

        # Invalid role: not Role enum
        peer_announcement = PeerAnnouncement("INVALID_ROLE", "test_session_1", PortType.VIDEO.value)
        client_addr = ("192.168.1.100", 54321)

        server._handle_peer_announcement(peer_announcement, client_addr)

        self.assertNotIn("test_session_1", server.relay.sessions)
        server.shutdown()

    @patch('socket.socket')
    def test_peer_announcement_packet_detection(self, mock_socket_class):
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

        # Test peer announcement packet detection
        peer_announcement_data = b'\x83\xa1t\xb0PeerAnnouncement' + b'rest_of_data'
        regular_data = b'regular_packet_data'

        client_addr = ("192.168.1.100", 54321)

        # Ensure Message.from_bytes returns a real PeerAnnouncement (so isinstance() is True)
        with patch.object(server, '_handle_peer_announcement') as mock_handle_announcement:
            with patch('v3xctrl_udp_relay.UDPRelayServer.Message') as mock_message_class:
                # return a real PeerAnnouncement instance (use your helper)
                real_peer_msg = self._build_announce("test_session_1", Role.STREAMER, PortType.VIDEO)
                mock_message_class.from_bytes.return_value = real_peer_msg

                # Handle peer announcement packet
                server._handle_packet(peer_announcement_data, client_addr)

                # Verify peer announcement handler was called with the real object
                mock_handle_announcement.assert_called_once_with(real_peer_msg, client_addr)

        # For regular packets, we expect them to be forwarded to PacketRelay.
        # PacketRelay.forward_packet is called with the server's UDP socket object
        with patch.object(server.relay, 'forward_packet') as mock_forward:
            server._handle_packet(regular_data, client_addr)

            # Assert it was called with the actual socket attribute from the server
            mock_forward.assert_called_once_with(regular_data, client_addr)

        server.shutdown()

    @patch('socket.socket')
    def test_send_peer_info_error_handling(self, mock_socket_class):
        mock_udp_socket = Mock()
        mock_command_socket = Mock()

        # Make sendto raise an exception
        mock_udp_socket.sendto.side_effect = Exception("Network error")

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

        # Create peers dict manually
        from v3xctrl_udp_relay.custom_types import PeerEntry

        peer_entry = PeerEntry(("192.168.1.100", 54321))

        # create a session manually
        session = Session("test_session_1")

        # add one peer to simulate a ready session
        session.register(Role.STREAMER, PortType.VIDEO, ("127.0.0.1", 50000))
        session.register(Role.VIEWER, PortType.VIDEO, ("127.0.0.1", 50001))

        # Call the relay's method (the UDPRelayServer doesn't expose _send_peer_info itself)
        server.relay._send_peer_info(session)

        # Verify sendto was attempted (even though it raised)
        mock_udp_socket.sendto.assert_called()

        server.shutdown()


    @patch('socket.socket')
    def test_find_role_for_address(self, mock_socket_class):
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

        # Create a mock session with roles
        from v3xctrl_udp_relay.custom_types import Session, PeerEntry
        mock_session = Mock(spec=Session)
        mock_session.roles = {
            Role.STREAMER: {
                PortType.VIDEO: PeerEntry(("192.168.1.100", 54321))
            }
        }

        addr = ("192.168.1.100", 54321)

        # Test finding role for existing address
        result = server._find_role_for_address(mock_session, addr)
        self.assertIsNotNone(result)
        role, port_type = result
        self.assertEqual(role, Role.STREAMER)
        self.assertEqual(port_type, PortType.VIDEO)

        # Test finding role for non-existing address
        result = server._find_role_for_address(mock_session, ("192.168.1.999", 99999))
        self.assertIsNone(result)

        server.shutdown()

    @patch('socket.socket')
    def test_cleanup_expired_entries(self, mock_socket_class):
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

        # Mock the cleanup method to verify it's called
        with patch.object(server.relay, 'cleanup_expired_mappings') as mock_cleanup:
            # Start the server threads
            with patch('threading.Thread') as mock_thread:
                mock_thread_instance = Mock()
                mock_thread.return_value = mock_thread_instance

                server.start()

                # Verify cleanup thread was created
                cleanup_calls = [call for call in mock_thread.call_args_list
                               if call[1]['target'] == server._cleanup_expired_entries]
                self.assertEqual(len(cleanup_calls), 1)

        server.shutdown()


if __name__ == '__main__':
    unittest.main()
