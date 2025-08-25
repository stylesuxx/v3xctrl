import json
import os
import socket
import threading
import unittest
from unittest.mock import Mock, patch, call, MagicMock
from concurrent.futures import ThreadPoolExecutor

from v3xctrl_control.message import PeerAnnouncement
from v3xctrl_udp_relay.UDPRelayServer import UDPRelayServer
from v3xctrl_udp_relay.custom_types import (
  Role,
  PortType,
  PeerEntry,
  RegistrationResult,
  SessionNotFoundError,
  Session
)


class TestUDPRelayServer(unittest.TestCase):
    def setUp(self):
        self.ip = "127.0.0.1"
        self.port = 8080
        self.db_path = "/tmp/test.db"

        # Basic mocks that all tests will need
        self.mock_socket = Mock()
        self.mock_command_socket = Mock()
        self.mock_executor = Mock()
        self.mock_thread = Mock()

    def tearDown(self):
        # Clean up any patches
        patch.stopall()

    def _create_server(self):
        """Helper method to create server with all necessary mocking"""
        with patch('socket.socket') as mock_socket_constructor, \
             patch('v3xctrl_udp_relay.UDPRelayServer.ThreadPoolExecutor', return_value=self.mock_executor), \
             patch('os.path.exists', return_value=True), \
             patch('os.unlink'), \
             patch('time.sleep'), \
             patch('threading.Thread', return_value=self.mock_thread), \
             patch('threading.Event') as mock_event:

            def socket_side_effect(family, type_):
                if family == socket.AF_UNIX:
                    return self.mock_command_socket
                elif family == socket.AF_INET:
                    return self.mock_socket
                return Mock()

            mock_socket_constructor.side_effect = socket_side_effect

            # Mock the threading event to prevent infinite loops
            mock_event_instance = Mock()
            mock_event_instance.is_set.return_value = False
            mock_event.return_value = mock_event_instance

            # Create server with command socket setup disabled
            with patch.object(UDPRelayServer, '_setup_command_socket'):
                server = UDPRelayServer(self.ip, self.port, self.db_path)
                server.running = mock_event_instance
                server.command_sock = self.mock_command_socket
                return server

    def test_initialization(self):
        server = self._create_server()
        self.assertEqual(server.ip, self.ip)
        self.assertEqual(server.port, self.port)
        self.assertEqual(server.TIMEOUT, 450)  # 3600 // 8
        self.assertEqual(server.CLEANUP_INTERVAL, 1)
        self.assertEqual(server.RECEIVE_BUFFER, 2048)
        self.assertEqual(server.COMMAND_SOCKET_PATH, "/tmp/udp_relay_command.sock")

        # Check socket configuration
        self.mock_socket.setsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.mock_socket.bind.assert_called_once_with(('0.0.0.0', self.port))

        # Check thread configuration
        self.assertTrue(server.daemon)
        self.assertEqual(server.name, "UDPRelayServer")

    def test_handle_commands_stops_when_running_false(self):
        server = self._create_server()
        server.running.is_set.return_value = False
        self.mock_command_socket.accept.side_effect = OSError("Test shutdown")

        server._handle_commands()

    def test_process_command_stats(self):
        server = self._create_server()
        mock_client_sock = Mock()
        mock_client_sock.recv.return_value = b"stats"

        mock_stats = {"session1": {"created_at": 12345, "mappings": []}}
        expected_response = json.dumps(mock_stats, indent=2)

        with patch.object(server, '_get_session_stats', return_value=mock_stats) as mock_get_stats:
            server._process_command(mock_client_sock)

            mock_get_stats.assert_called_once()
            mock_client_sock.send.assert_called_once_with(expected_response.encode('utf-8'))
            mock_client_sock.close.assert_called_once()

    def test_process_command_unknown_command(self):
        server = self._create_server()
        mock_client_sock = Mock()
        mock_client_sock.recv.return_value = b"unknown"

        server._process_command(mock_client_sock)

        mock_client_sock.send.assert_called_once_with(b"Unknown command")
        mock_client_sock.close.assert_called_once()

    def test_process_command_exception_handling(self):
        server = self._create_server()
        mock_client_sock = Mock()
        mock_client_sock.recv.side_effect = Exception("Connection error")

        with patch('logging.error') as mock_log:
            server._process_command(mock_client_sock)

            mock_log.assert_called_once()
            args = mock_log.call_args[0]
            self.assertIn("Error processing command", args[0])
            mock_client_sock.close.assert_called_once()

    def test_get_session_stats_empty(self):
        server = self._create_server()
        server.registry.sessions = {}

        stats = server._get_session_stats()

        self.assertEqual(stats, {})

    def test_get_session_stats_with_sessions(self):
        server = self._create_server()

        # Mock session data
        session1 = Mock(spec=Session)
        session1.created_at = 1234567890
        session1.roles = {
            Role.STREAMER: {
                PortType.VIDEO: Mock(addr=("1.1.1.1", 1111)),
                PortType.CONTROL: Mock(addr=("1.1.1.2", 1112))
            }
        }

        server.registry.sessions = {"session1": session1}

        # Mock relay data - use list instead of set to ensure order
        server.relay.session_to_addresses = {
            "session1": [("1.1.1.1", 1111), ("1.1.1.2", 1112)]
        }
        server.relay.relay_map = {
            ("1.1.1.1", 1111): Mock(),
            ("1.1.1.2", 1112): Mock()
        }

        with patch.object(server, '_find_role_for_address') as mock_find_role:
            mock_find_role.side_effect = [
                (Role.STREAMER, PortType.VIDEO),
                (Role.STREAMER, PortType.CONTROL)
            ]

            stats = server._get_session_stats()

            # Check the structure but don't rely on ordering
            self.assertEqual(len(stats), 1)
            self.assertIn("session1", stats)
            session_stats = stats["session1"]
            self.assertEqual(session_stats["created_at"], 1234567890)
            self.assertEqual(len(session_stats["mappings"]), 2)

            # Check that both expected mappings are present (order independent)
            addresses = [mapping["address"] for mapping in session_stats["mappings"]]
            self.assertIn("1.1.1.1:1111", addresses)
            self.assertIn("1.1.1.2:1112", addresses)

    def test_get_session_stats_no_role_found(self):
        server = self._create_server()

        session1 = Mock(spec=Session)
        session1.created_at = 1234567890

        server.registry.sessions = {"session1": session1}
        server.relay.session_to_addresses = {"session1": {("1.1.1.1", 1111)}}
        server.relay.relay_map = {("1.1.1.1", 1111): Mock()}

        with patch.object(server, '_find_role_for_address', return_value=None):
            stats = server._get_session_stats()

            expected = {
                "session1": {
                    "created_at": 1234567890,
                    "mappings": []
                }
            }

            self.assertEqual(stats, expected)

    def test_find_role_for_address_found(self):
        server = self._create_server()

        mock_session = Mock(spec=Session)
        mock_session.roles = {
            Role.STREAMER: {
                PortType.VIDEO: Mock(addr=("1.1.1.1", 1111)),
                PortType.CONTROL: Mock(addr=("1.1.1.2", 1112))
            },
            Role.VIEWER: {
                PortType.VIDEO: Mock(addr=("2.2.2.1", 2221))
            }
        }

        result = server._find_role_for_address(mock_session, ("1.1.1.2", 1112))

        self.assertEqual(result, (Role.STREAMER, PortType.CONTROL))

    def test_find_role_for_address_not_found(self):
        server = self._create_server()

        mock_session = Mock(spec=Session)
        mock_session.roles = {
            Role.STREAMER: {
                PortType.VIDEO: Mock(addr=("1.1.1.1", 1111))
            }
        }

        result = server._find_role_for_address(mock_session, ("9.9.9.9", 9999))

        self.assertIsNone(result)

    def test_handle_peer_announcement_invalid_role(self):
        server = self._create_server()

        mock_announcement = Mock(spec=PeerAnnouncement)
        mock_announcement.get_role.return_value = "invalid_role"
        mock_announcement.get_port_type.return_value = "video"
        mock_announcement.get_id.return_value = "session123"

        server._handle_peer_announcement(mock_announcement, ("1.1.1.1", 1111))

        # Should not register anything
        self.assertEqual(len(server.registry.sessions), 0)

    def test_handle_peer_announcement_invalid_port_type(self):
        server = self._create_server()

        mock_announcement = Mock(spec=PeerAnnouncement)
        mock_announcement.get_role.return_value = "streamer"
        mock_announcement.get_port_type.return_value = "invalid_port"
        mock_announcement.get_id.return_value = "session123"

        server._handle_peer_announcement(mock_announcement, ("1.1.1.1", 1111))

        # Should not register anything
        self.assertEqual(len(server.registry.sessions), 0)

    def test_handle_peer_announcement_session_not_found(self):
        server = self._create_server()

        mock_announcement = Mock(spec=PeerAnnouncement)
        mock_announcement.get_role.return_value = "streamer"
        mock_announcement.get_port_type.return_value = "video"
        mock_announcement.get_id.return_value = "nonexistent_session"

        # Mock registry to return session not found
        with patch.object(server.registry, 'register_peer') as mock_register:
            mock_register.return_value = RegistrationResult(
                error=SessionNotFoundError("Session not found")
            )

            with patch('logging.info') as mock_log:
                server._handle_peer_announcement(mock_announcement, ("1.1.1.1", 1111))

            mock_log.assert_called_once_with("Ignoring announcement for unknown session 'nonexistent_session' from ('1.1.1.1', 1111)")

    def test_handle_peer_announcement_session_not_found_sends_error(self):
        server = self._create_server()

        mock_announcement = Mock(spec=PeerAnnouncement)
        mock_announcement.get_role.return_value = "streamer"
        mock_announcement.get_port_type.return_value = "video"
        mock_announcement.get_id.return_value = "nonexistent_session"

        with patch.object(server.registry, 'register_peer') as mock_register:
            mock_register.return_value = RegistrationResult(
                error=SessionNotFoundError("Session not found")
            )

            with patch('v3xctrl_udp_relay.UDPRelayServer.Error') as mock_error_class:
                mock_error = Mock()
                mock_error.to_bytes.return_value = b"error_data"
                mock_error_class.return_value = mock_error

                server._handle_peer_announcement(mock_announcement, ("1.1.1.1", 1111))

                mock_error_class.assert_called_once_with("403")
                self.mock_socket.sendto.assert_called_once_with(b"error_data", ("1.1.1.1", 1111))

    def test_handle_peer_announcement_error_sending_error_message(self):
        server = self._create_server()

        mock_announcement = Mock(spec=PeerAnnouncement)
        mock_announcement.get_role.return_value = "streamer"
        mock_announcement.get_port_type.return_value = "video"
        mock_announcement.get_id.return_value = "nonexistent_session"

        with patch.object(server.registry, 'register_peer') as mock_register:
            mock_register.return_value = RegistrationResult(
                error=SessionNotFoundError("Session not found")
            )

            # Make socket.sendto raise an exception
            self.mock_socket.sendto.side_effect = Exception("Network error")

            with patch('logging.error') as mock_log:
                server._handle_peer_announcement(mock_announcement, ("1.1.1.1", 1111))

                mock_log.assert_called_once()
                args, kwargs = mock_log.call_args
                self.assertIn("Failed to send error message", args[0])
                self.assertEqual(kwargs['exc_info'], True)

    def test_handle_peer_announcement_new_peer_not_ready(self):
        server = self._create_server()

        mock_announcement = Mock(spec=PeerAnnouncement)
        mock_announcement.get_role.return_value = "streamer"
        mock_announcement.get_port_type.return_value = "video"
        mock_announcement.get_id.return_value = "session123"

        with patch.object(server.registry, 'register_peer') as mock_register:
            mock_register.return_value = RegistrationResult(
                is_new_peer=True,
                session_ready=False
            )

            with patch('logging.info') as mock_log:
                server._handle_peer_announcement(mock_announcement, ("1.1.1.1", 1111))

                mock_log.assert_called_once_with("session123: Registered STREAMER:VIDEO from ('1.1.1.1', 1111)")

    def test_handle_peer_announcement_existing_peer(self):
        server = self._create_server()

        mock_announcement = Mock(spec=PeerAnnouncement)
        mock_announcement.get_role.return_value = "viewer"
        mock_announcement.get_port_type.return_value = "control"
        mock_announcement.get_id.return_value = "session123"

        with patch.object(server.registry, 'register_peer') as mock_register:
            mock_register.return_value = RegistrationResult(
                is_new_peer=False,
                session_ready=False
            )

            with patch('logging.info') as mock_log:
                server._handle_peer_announcement(mock_announcement, ("1.1.1.1", 1111))

                mock_log.assert_not_called()

    def test_handle_peer_announcement_session_ready(self):
        server = self._create_server()

        mock_announcement = Mock(spec=PeerAnnouncement)
        mock_announcement.get_role.return_value = "viewer"
        mock_announcement.get_port_type.return_value = "control"
        mock_announcement.get_id.return_value = "session123"

        mock_peers = {
            Role.STREAMER: {
                PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
            },
            Role.VIEWER: {
                PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
            }
        }

        with patch.object(server.registry, 'register_peer') as mock_register:
            mock_register.return_value = RegistrationResult(
                is_new_peer=True,
                session_ready=True
            )

            with patch.object(server.registry, 'get_session_peers') as mock_get_peers:
                mock_get_peers.return_value = mock_peers

                with patch.object(server.relay, 'update_mapping') as mock_update:
                    with patch.object(server, '_send_peer_info') as mock_send:
                        with patch('logging.info') as mock_log:
                            server._handle_peer_announcement(mock_announcement, ("2.2.2.2", 2222))

                            mock_update.assert_called_once_with("session123", mock_peers)
                            mock_send.assert_called_once_with(mock_peers)

                            # Check both log messages
                            expected_calls = [
                                call("session123: Registered VIEWER:CONTROL from ('2.2.2.2', 2222)"),
                                call("session123: Session ready, peer info exchanged")
                            ]
                            mock_log.assert_has_calls(expected_calls)

    def test_send_peer_info_success(self):
        server = self._create_server()

        peers = {
            Role.STREAMER: {
                PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
            },
            Role.VIEWER: {
                PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
            }
        }

        with patch('v3xctrl_udp_relay.UDPRelayServer.PeerInfo') as mock_peer_info_class:
            mock_peer_info = Mock()
            mock_peer_info.to_bytes.return_value = b"peer_info_data"
            mock_peer_info_class.return_value = mock_peer_info

            server._send_peer_info(peers)

            mock_peer_info_class.assert_called_once_with(
                ip=self.ip,
                video_port=self.port,
                control_port=self.port
            )

            # Should send to all 4 peers
            expected_calls = [
                call(b"peer_info_data", ("1.1.1.1", 1111)),
                call(b"peer_info_data", ("1.1.1.2", 1112)),
                call(b"peer_info_data", ("2.2.2.1", 2221)),
                call(b"peer_info_data", ("2.2.2.2", 2222))
            ]
            self.mock_socket.sendto.assert_has_calls(expected_calls, any_order=True)

    def test_send_peer_info_socket_error(self):
        server = self._create_server()

        peers = {
            Role.STREAMER: {
                PortType.VIDEO: PeerEntry(("1.1.1.1", 1111))
            }
        }

        self.mock_socket.sendto.side_effect = Exception("Network error")

        with patch('logging.error') as mock_log:
            server._send_peer_info(peers)

            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            self.assertIn("Error sending PeerInfo", args[0])
            self.assertEqual(kwargs['exc_info'], True)

    def test_cleanup_expired_entries(self):
        server = self._create_server()
        expired_sessions = {"session1", "session2"}

        with patch.object(server.relay, 'cleanup_expired_mappings') as mock_cleanup_mappings:
            mock_cleanup_mappings.return_value = expired_sessions

            with patch.object(server.registry, 'remove_expired_sessions') as mock_remove_sessions:
                with patch('time.sleep') as mock_sleep:
                    # Mock running.is_set to return True once, then False to exit loop
                    server.running.is_set.side_effect = [True, False]

                    server._cleanup_expired_entries()

                    mock_cleanup_mappings.assert_called_once()
                    mock_remove_sessions.assert_called_once_with(expired_sessions)
                    mock_sleep.assert_called_once_with(1)

    def test_handle_packet_peer_announcement(self):
        server = self._create_server()
        peer_announcement_data = b'\x83\xa1t\xb0PeerAnnouncement' + b'extra_data'

        mock_announcement = Mock(spec=PeerAnnouncement)

        with patch('v3xctrl_udp_relay.UDPRelayServer.Message') as mock_message_class:
            mock_message_class.from_bytes.return_value = mock_announcement

            with patch.object(server, '_handle_peer_announcement') as mock_handle:
                server._handle_packet(peer_announcement_data, ("1.1.1.1", 1111))

                mock_message_class.from_bytes.assert_called_once_with(peer_announcement_data)
                mock_handle.assert_called_once_with(mock_announcement, ("1.1.1.1", 1111))

    def test_handle_packet_peer_announcement_not_peer_announcement_type(self):
        server = self._create_server()
        peer_announcement_data = b'\x83\xa1t\xb0PeerAnnouncement' + b'extra_data'

        mock_other_message = Mock()  # Not a PeerAnnouncement

        with patch('v3xctrl_udp_relay.UDPRelayServer.Message') as mock_message_class:
            mock_message_class.from_bytes.return_value = mock_other_message

            with patch.object(server, '_handle_peer_announcement') as mock_handle:
                with patch.object(server.relay, 'forward_packet') as mock_forward:
                    server._handle_packet(peer_announcement_data, ("1.1.1.1", 1111))

                    mock_handle.assert_not_called()
                    mock_forward.assert_called_once_with(self.mock_socket, peer_announcement_data, ("1.1.1.1", 1111))

    def test_handle_packet_peer_announcement_parse_error(self):
        server = self._create_server()
        peer_announcement_data = b'\x83\xa1t\xb0PeerAnnouncement' + b'invalid_data'

        with patch('v3xctrl_udp_relay.UDPRelayServer.Message') as mock_message_class:
            mock_message_class.from_bytes.side_effect = Exception("Parse error")

            with patch.object(server, '_handle_peer_announcement') as mock_handle:
                with patch.object(server.relay, 'forward_packet') as mock_forward:
                    server._handle_packet(peer_announcement_data, ("1.1.1.1", 1111))

                    mock_handle.assert_not_called()
                    mock_forward.assert_not_called()

    def test_handle_packet_regular_packet(self):
        server = self._create_server()
        regular_data = b'regular_packet_data'

        with patch.object(server.relay, 'forward_packet') as mock_forward:
            server._handle_packet(regular_data, ("1.1.1.1", 1111))

            mock_forward.assert_called_once_with(self.mock_socket, regular_data, ("1.1.1.1", 1111))

    def test_handle_packet_forward_error(self):
        server = self._create_server()
        regular_data = b'regular_packet_data'

        with patch.object(server.relay, 'forward_packet') as mock_forward:
            mock_forward.side_effect = Exception("Forward error")

            with patch('logging.error') as mock_log:
                server._handle_packet(regular_data, ("1.1.1.1", 1111))

                mock_log.assert_called_once()
                args, kwargs = mock_log.call_args
                self.assertIn("Error handling packet", args[0])
                self.assertEqual(kwargs['exc_info'], True)

    def test_run_starts_cleanup_thread(self):
        server = self._create_server()

        with patch('threading.Thread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread

            # Clear running flag so OSError will break the loop
            server.running.is_set.return_value = False
            self.mock_socket.recvfrom.side_effect = OSError("Stopped")

            with patch('logging.info'):
                server.run()

                # Should call Thread for cleanup
                mock_thread_class.assert_called_with(
                    target=server._cleanup_expired_entries,
                    daemon=True
                )
                mock_thread.start.assert_called_once()

    def test_shutdown(self):
        server = self._create_server()

        server.shutdown()

        self.assertFalse(server.running.is_set())
        self.mock_socket.close.assert_called_once()
        self.mock_command_socket.close.assert_called_once()

    def test_shutdown_socket_close_error(self):
        server = self._create_server()
        self.mock_socket.close.side_effect = Exception("Close error")

        with patch('logging.warning') as mock_log:
            server.shutdown()

            self.assertFalse(server.running.is_set())
            mock_log.assert_called()

    def test_shutdown_command_socket_close_error(self):
        server = self._create_server()
        self.mock_command_socket.close.side_effect = Exception("Command socket close error")

        with patch('logging.warning') as mock_log:
            server.shutdown()

            self.assertFalse(server.running.is_set())
            mock_log.assert_called()

    def test_integration_full_peer_announcement_flow(self):
        """Test the complete flow from receiving peer announcement to session ready"""
        server = self._create_server()

        # Mock the registry.register_peer to simulate the complete flow
        registration_results = [
            RegistrationResult(is_new_peer=True, session_ready=False),  # First peer
            RegistrationResult(is_new_peer=True, session_ready=False),  # Second peer
            RegistrationResult(is_new_peer=True, session_ready=False),  # Third peer
            RegistrationResult(is_new_peer=True, session_ready=True)    # Fourth peer - session ready
        ]

        mock_peers = {
            Role.STREAMER: {
                PortType.VIDEO: PeerEntry(("1.1.1.1", 1111)),
                PortType.CONTROL: PeerEntry(("1.1.1.2", 1112))
            },
            Role.VIEWER: {
                PortType.VIDEO: PeerEntry(("2.2.2.1", 2221)),
                PortType.CONTROL: PeerEntry(("2.2.2.2", 2222))
            }
        }

        # Create mock announcements
        streamer_video = Mock(spec=PeerAnnouncement)
        streamer_video.get_role.return_value = "streamer"
        streamer_video.get_port_type.return_value = "video"
        streamer_video.get_id.return_value = "session123"

        streamer_control = Mock(spec=PeerAnnouncement)
        streamer_control.get_role.return_value = "streamer"
        streamer_control.get_port_type.return_value = "control"
        streamer_control.get_id.return_value = "session123"

        viewer_video = Mock(spec=PeerAnnouncement)
        viewer_video.get_role.return_value = "viewer"
        viewer_video.get_port_type.return_value = "video"
        viewer_video.get_id.return_value = "session123"

        viewer_control = Mock(spec=PeerAnnouncement)
        viewer_control.get_role.return_value = "viewer"
        viewer_control.get_port_type.return_value = "control"
        viewer_control.get_id.return_value = "session123"

        with patch.object(server.registry, 'register_peer', side_effect=registration_results) as mock_register:
            with patch.object(server.registry, 'get_session_peers', return_value=mock_peers) as mock_get_peers:
                with patch.object(server.relay, 'update_mapping') as mock_update_mapping:
                    with patch.object(server, '_send_peer_info') as mock_send:
                        with patch('logging.info'):
                            # Register all peers
                            server._handle_peer_announcement(streamer_video, ("1.1.1.1", 1111))
                            server._handle_peer_announcement(streamer_control, ("1.1.1.2", 1112))
                            server._handle_peer_announcement(viewer_video, ("2.2.2.1", 2221))

                            # This should make the session ready
                            server._handle_peer_announcement(viewer_control, ("2.2.2.2", 2222))

                            # Verify all registrations were called
                            self.assertEqual(mock_register.call_count, 4)

                            # Verify session ready actions were triggered only once (on the last registration)
                            mock_get_peers.assert_called_once_with("session123")
                            mock_update_mapping.assert_called_once_with("session123", mock_peers)
                            mock_send.assert_called_once_with(mock_peers)

    def test_byte_prefix_detection_performance(self):
        """Test that the byte prefix detection is actually faster than full parsing"""
        server = self._create_server()
        non_announcement_data = b'regular_packet_data'

        with patch('v3xctrl_udp_relay.UDPRelayServer.Message') as mock_message_class:
            with patch.object(server.relay, 'forward_packet') as mock_forward:
                server._handle_packet(non_announcement_data, ("1.1.1.1", 1111))

                # Message.from_bytes should never be called for non-announcement data
                mock_message_class.from_bytes.assert_not_called()
                mock_forward.assert_called_once()

    def test_timeout_constant_updated(self):
        """Test that TIMEOUT constant reflects the new value"""
        self.assertEqual(UDPRelayServer.TIMEOUT, 450)  # 3600 // 8

    def test_cleanup_uses_new_api(self):
        """Test that cleanup uses the new PacketRelay -> PeerRegistry API"""
        server = self._create_server()
        expired_sessions = {"expired1", "expired2"}

        with patch.object(server.relay, 'cleanup_expired_mappings', return_value=expired_sessions) as mock_relay_cleanup:
            with patch.object(server.registry, 'remove_expired_sessions') as mock_registry_remove:
                with patch('time.sleep'):
                    # Run one iteration of cleanup
                    server.running.is_set.side_effect = [True, False]
                    server._cleanup_expired_entries()

                # Verify the new API is used correctly
                mock_relay_cleanup.assert_called_once()
                mock_registry_remove.assert_called_once_with(expired_sessions)


if __name__ == '__main__':
    unittest.main()
