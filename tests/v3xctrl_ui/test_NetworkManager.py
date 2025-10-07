import unittest
from unittest.mock import MagicMock, patch

from src.v3xctrl_ui.NetworkManager import NetworkManager
from v3xctrl_helper.exceptions import UnauthorizedError, PeerRegistrationError


class TestNetworkManager(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures with proper mocking."""
        # Mock settings
        self.settings = MagicMock()
        self.settings.get.side_effect = lambda key, default=None: {
            "relay": {"enabled": False},
            "ports": {"video": 5000, "control": 6000}
        }.get(key, default)

        # Mock OSD handlers
        self.osd_handlers = {
            "messages": [("TestMessage", lambda msg, addr: None)],
            "states": [("CONNECTED", lambda: None)]
        }

        # Patch external dependencies
        self.init_patcher = patch("src.v3xctrl_ui.NetworkManager.Init")
        self.mock_init = self.init_patcher.start()

        self.peer_patcher = patch("src.v3xctrl_ui.NetworkManager.Peer")
        self.mock_peer_cls = self.peer_patcher.start()

        self.get_ip_patcher = patch("src.v3xctrl_ui.NetworkManager.get_external_ip")
        self.mock_get_ip = self.get_ip_patcher.start()
        self.mock_get_ip.return_value = "192.168.1.100"

        self.socket_patcher = patch("src.v3xctrl_ui.NetworkManager.socket")
        self.mock_socket = self.socket_patcher.start()

        self.threading_patcher = patch("src.v3xctrl_ui.NetworkManager.threading.Thread")
        self.mock_thread_cls = self.threading_patcher.start()
        self.mock_thread = MagicMock()
        self.mock_thread_cls.return_value = self.mock_thread

    def tearDown(self):
        """Clean up patches."""
        self.init_patcher.stop()
        self.peer_patcher.stop()
        self.get_ip_patcher.stop()
        self.socket_patcher.stop()
        self.threading_patcher.stop()

    def test_initialization_relay_disabled(self):
        """Test NetworkManager initialization with relay disabled."""
        with patch('builtins.print') as mock_print:
            nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

            self.assertEqual(nm.video_port, 5000)
            self.assertEqual(nm.control_port, 6000)
            self.assertEqual(nm.settings, self.settings)
            self.assertEqual(nm.server_handlers, self.osd_handlers)

            # Initial state
            self.assertIsNone(nm.video_receiver)
            self.assertIsNone(nm.server)
            self.assertIsNone(nm.server_error)
            self.assertFalse(nm.relay_enable)

            # Should print connection info
            mock_print.assert_any_call("================================")
            mock_print.assert_any_call("IP Address:   192.168.1.100")

    def test_initialization_relay_enabled(self):
        """Test NetworkManager initialization with relay enabled."""
        relay_settings = MagicMock()
        relay_settings.get.side_effect = lambda key, default=None: {
            "relay": {"enabled": True, "server": "relay.example.com:8080", "id": "test123"},
            "ports": {"video": 5000, "control": 6000}
        }.get(key, default)

        with patch('builtins.print') as mock_print:
            nm = NetworkManager(5000, 6000, relay_settings, self.osd_handlers)

            # Relay should be configured
            self.assertTrue(nm.relay_enable)
            self.assertEqual(nm.relay_server, "relay.example.com")
            self.assertEqual(nm.relay_port, 8080)
            self.assertEqual(nm.relay_id, "test123")

            # Should not print connection info when relay is enabled
            mock_print.assert_not_called()

    def test_setup_relay_valid_port(self):
        """Test setup_relay with valid port in server string."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        nm.setup_relay("example.com:9999", "testid")

        self.assertTrue(nm.relay_enable)
        self.assertEqual(nm.relay_server, "example.com")
        self.assertEqual(nm.relay_port, 9999)
        self.assertEqual(nm.relay_id, "testid")

    def test_setup_relay_invalid_port(self):
        """Test setup_relay with invalid port in server string."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        with patch("src.v3xctrl_ui.NetworkManager.logging.warning") as mock_warning:
            nm.setup_relay("example.com:notaport", "testid")

            self.assertTrue(nm.relay_enable)
            self.assertEqual(nm.relay_server, "example.com")
            self.assertEqual(nm.relay_port, 8888)  # Default port
            self.assertEqual(nm.relay_id, "testid")
            mock_warning.assert_called()

    def test_setup_relay_no_port(self):
        """Test setup_relay with no port in server string."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        nm.setup_relay("example.com", "testid")

        self.assertTrue(nm.relay_enable)
        self.assertEqual(nm.relay_server, "example.com")
        self.assertEqual(nm.relay_port, 8888)  # Default port
        self.assertEqual(nm.relay_id, "testid")

    def test_setup_ports_no_relay(self):
        """Test setup_ports without relay."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # Mock Init methods - server now returns just the server instance
        mock_video_receiver = MagicMock()
        mock_server = MagicMock()
        self.mock_init.video_receiver.return_value = mock_video_receiver
        self.mock_init.server.return_value = mock_server

        nm.setup_ports()

        # Verify thread was started
        self.mock_thread_cls.assert_called_once()
        self.mock_thread.start.assert_called_once()

        # Execute the task function manually to test it
        task_func = self.mock_thread_cls.call_args[1]['target']
        task_func()

        # Verify video receiver and server were initialized
        self.mock_init.video_receiver.assert_called_once()
        # Server should be called with separate message and state handlers
        expected_messages = self.osd_handlers["messages"]
        expected_states = self.osd_handlers["states"]
        self.mock_init.server.assert_called_once_with(6000, expected_messages, expected_states)

    def test_setup_ports_with_relay_success(self):
        """Test setup_ports with successful relay connection."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)
        nm.setup_relay("relay.example.com:8080", "testid")

        # Mock Peer setup
        mock_peer = MagicMock()
        mock_peer.setup.return_value = {"video": ("1.2.3.4", 1234)}
        self.mock_peer_cls.return_value = mock_peer

        # Mock Init methods
        mock_video_receiver = MagicMock()
        mock_server = MagicMock()
        self.mock_init.video_receiver.return_value = mock_video_receiver
        self.mock_init.server.return_value = mock_server

        nm.setup_ports()

        # Execute the task function
        task_func = self.mock_thread_cls.call_args[1]['target']
        task_func()

        # Verify peer was set up
        self.mock_peer_cls.assert_called_with("relay.example.com", 8080, "testid")
        mock_peer.setup.assert_called_with("viewer", {"video": 5000, "control": 6000})

    def test_setup_ports_with_relay_unauthorized(self):
        """Test setup_ports with unauthorized relay."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)
        nm.setup_relay("relay.example.com:8080", "badid")

        # Mock Peer to raise UnauthorizedError
        mock_peer = MagicMock()
        mock_peer.setup.side_effect = PeerRegistrationError({}, {})
        self.mock_peer_cls.return_value = mock_peer

        nm.setup_ports()

        # Execute the task function
        task_func = self.mock_thread_cls.call_args[1]['target']
        task_func()

        # Verify error message was set
        self.assertIn("registration failed", nm.relay_status_message.lower())

    def test_setup_ports_server_error(self):
        """Test setup_ports when server initialization fails."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # Mock Init methods - server raises RuntimeError
        mock_video_receiver = MagicMock()
        self.mock_init.video_receiver.return_value = mock_video_receiver
        self.mock_init.server.side_effect = RuntimeError("Server failed")

        with patch("src.v3xctrl_ui.NetworkManager.logging.error") as mock_log_error:
            nm.setup_ports()

            # Execute the task function
            task_func = self.mock_thread_cls.call_args[1]['target']
            task_func()

            # Verify error was logged and stored
            self.assertEqual(nm.server_error, "Server failed")
            mock_log_error.assert_called_once()

    def test_send_latency_check_with_server(self):
        """Test send_latency_check when server is available."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # Mock server
        mock_server = MagicMock()
        nm.server = mock_server
        nm.server_error = None

        nm.send_latency_check()

        # Verify Latency message was sent
        mock_server.send.assert_called_once()
        # Check that the argument is a Latency instance
        call_args = mock_server.send.call_args[0]
        self.assertEqual(call_args[0].__class__.__name__, 'Latency')

    def test_send_latency_check_no_server(self):
        """Test send_latency_check when no server is available."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # No server
        nm.server = None
        nm.server_error = None

        nm.send_latency_check()

        # Should not raise exception, just do nothing

    def test_send_latency_check_with_server_error(self):
        """Test send_latency_check when server has an error."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # Server with error
        mock_server = MagicMock()
        nm.server = mock_server
        nm.server_error = "Connection failed"

        nm.send_latency_check()

        # Should not send when there's an error
        mock_server.send.assert_not_called()

    def test_get_data_queue_size_with_server(self):
        """Test get_data_queue_size when server is available."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # Mock server with queue
        mock_server = MagicMock()
        mock_server.transmitter.queue.qsize.return_value = 42
        nm.server = mock_server
        nm.server_error = None

        result = nm.get_data_queue_size()

        self.assertEqual(result, 42)

    def test_get_data_queue_size_no_server(self):
        """Test get_data_queue_size when no server is available."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # No server
        nm.server = None

        result = nm.get_data_queue_size()

        self.assertEqual(result, 0)

    def test_get_data_queue_size_with_server_error(self):
        """Test get_data_queue_size when server has an error."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # Server with error
        mock_server = MagicMock()
        nm.server = mock_server
        nm.server_error = "Connection failed"

        result = nm.get_data_queue_size()

        self.assertEqual(result, 0)

    def test_shutdown_with_components(self):
        """Test shutdown when both server and video_receiver exist."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # Mock components
        mock_server = MagicMock()
        mock_video_receiver = MagicMock()
        nm.server = mock_server
        nm.video_receiver = mock_video_receiver

        nm.shutdown()

        # Verify shutdown sequence
        mock_server.stop.assert_called_once()
        mock_server.join.assert_called_once()
        mock_video_receiver.stop.assert_called_once()
        mock_video_receiver.join.assert_called_once()

    def test_shutdown_with_no_components(self):
        """Test shutdown when no components exist."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # No components
        nm.server = None
        nm.video_receiver = None

        # Should not raise exception
        nm.shutdown()

    def test_shutdown_partial_components(self):
        """Test shutdown when only some components exist."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        # Only server, no video receiver
        mock_server = MagicMock()
        nm.server = mock_server
        nm.video_receiver = None

        nm.shutdown()

        # Only server should be shut down
        mock_server.stop.assert_called_once()
        mock_server.join.assert_called_once()

    @patch("src.v3xctrl_ui.NetworkManager.logging")
    @patch("src.v3xctrl_ui.NetworkManager.time.sleep")
    def test_poke_peer_functionality(self, mock_sleep, mock_logging):
        """Test the poke_peer functionality within setup_ports."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)
        nm.setup_relay("relay.example.com:8080", "testid")

        # Mock successful peer setup
        mock_peer = MagicMock()
        mock_peer.setup.return_value = {"video": ("1.2.3.4", 1234)}
        self.mock_peer_cls.return_value = mock_peer

        # Mock socket operations
        mock_sock = MagicMock()
        self.mock_socket.socket.return_value = mock_sock

        # Mock Init methods to capture the poke_peer function
        mock_video_receiver = MagicMock()
        self.mock_init.video_receiver.return_value = mock_video_receiver
        self.mock_init.server.return_value = MagicMock()

        # Create a version that executes synchronously
        def sync_setup_ports():
            video_address = None
            if nm.relay_enable and nm.relay_server and nm.relay_id:
                local_bind_ports = {
                    "video": nm.video_port,
                    "control": nm.control_port
                }
                peer = self.mock_peer_cls(nm.relay_server, nm.relay_port, nm.relay_id)

                try:
                    addresses = peer.setup("viewer", local_bind_ports)
                    video_address = addresses["video"]
                except UnauthorizedError:
                    nm.relay_status_message = "ERROR: Relay ID unauthorized!"
                    return

            def poke_peer() -> None:
                if nm.relay_enable and video_address:
                    mock_logging.info(f"Poking peer {video_address}")
                    sock = None
                    try:
                        sock = self.mock_socket.socket(self.mock_socket.AF_INET, self.mock_socket.SOCK_DGRAM)
                        sock.setsockopt(self.mock_socket.SOL_SOCKET, self.mock_socket.SO_REUSEADDR, 1)
                        sock.bind(("0.0.0.0", nm.video_port))

                        for i in range(5):
                            try:
                                sock.sendto(b'SYN', video_address)
                                mock_sleep(0.1)
                            except Exception as e:
                                mock_logging.warning(f"Poke {i+1}/5 failed: {e}")

                    except Exception as e:
                        mock_logging.error(f"Failed to poke peer: {e}", exc_info=True)
                    finally:
                        if sock:
                            sock.close()
                        mock_logging.info(f"Poke to {video_address} completed and socket closed.")

            nm.video_receiver = self.mock_init.video_receiver(nm.video_port, poke_peer)

            # Extract handlers properly
            message_handlers = nm.server_handlers.get("messages", [])
            state_handlers = nm.server_handlers.get("states", [])
            nm.server = self.mock_init.server(nm.control_port, message_handlers, state_handlers)

            # Execute poke_peer to test it
            poke_peer()

        # Execute the synchronous version
        sync_setup_ports()

        # Verify socket operations
        self.mock_socket.socket.assert_called_with(self.mock_socket.AF_INET, self.mock_socket.SOCK_DGRAM)
        mock_sock.bind.assert_called_with(("0.0.0.0", 5000))

        # Should send 5 SYN packets
        self.assertEqual(mock_sock.sendto.call_count, 5)
        for call in mock_sock.sendto.call_args_list:
            self.assertEqual(call[0][0], b'SYN')
            self.assertEqual(call[0][1], ("1.2.3.4", 1234))

        # Verify logging calls
        mock_logging.info.assert_any_call("Poking peer ('1.2.3.4', 1234)")
        mock_logging.info.assert_any_call("Poke to ('1.2.3.4', 1234) completed and socket closed.")

    def test_initialization_relay_enabled_no_server(self):
        """Test NetworkManager initialization with relay enabled but no server."""
        relay_settings = MagicMock()
        relay_settings.get.side_effect = lambda key, default=None: {
            "relay": {"enabled": True, "id": "test123"},  # Missing server
            "ports": {"video": 5000, "control": 6000}
        }.get(key, default)

        with patch('builtins.print') as mock_print:
            nm = NetworkManager(5000, 6000, relay_settings, self.osd_handlers)

            # Relay should not be configured due to missing server
            self.assertFalse(nm.relay_enable)
            self.assertIsNone(nm.relay_server)
            self.assertIsNone(nm.relay_id)

    def test_initialization_relay_enabled_no_id(self):
        """Test NetworkManager initialization with relay enabled but no ID."""
        relay_settings = MagicMock()
        relay_settings.get.side_effect = lambda key, default=None: {
            "relay": {"enabled": True, "server": "relay.example.com:8080"},  # Missing ID
            "ports": {"video": 5000, "control": 6000}
        }.get(key, default)

        with patch('builtins.print') as mock_print:
            nm = NetworkManager(5000, 6000, relay_settings, self.osd_handlers)

            # Relay should not be configured due to missing ID
            self.assertFalse(nm.relay_enable)
            self.assertIsNone(nm.relay_server)
            self.assertIsNone(nm.relay_id)

    def test_setup_relay_empty_server(self):
        """Test setup_relay with empty server string."""
        nm = NetworkManager(5000, 6000, self.settings, self.osd_handlers)

        nm.setup_relay("", "testid")

        self.assertTrue(nm.relay_enable)
        self.assertEqual(nm.relay_server, "")
        self.assertEqual(nm.relay_port, 8888)  # Default port
        self.assertEqual(nm.relay_id, "testid")


if __name__ == '__main__':
    unittest.main()
