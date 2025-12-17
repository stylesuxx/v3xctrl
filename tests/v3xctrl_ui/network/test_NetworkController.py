import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_ui.network.NetworkController import NetworkController
from v3xctrl_helper.exceptions import PeerRegistrationError


class TestNetworkController(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures with proper mocking."""
        # Mock settings
        self.settings = MagicMock()
        self.settings.get.side_effect = lambda key, default=None: {
            "relay": {"enabled": False},
            "ports": {"video": 5000, "control": 6000},
            "udp_packet_ttl": 100
        }.get(key, default)

        # Mock handlers
        self.handlers = {
            "messages": [("TestMessage", lambda msg, addr: None)],
            "states": [("CONNECTED", lambda: None)]
        }

        # Patch external dependencies
        self.server_patcher = patch("v3xctrl_ui.network.NetworkController.Server")
        self.mock_server_cls = self.server_patcher.start()
        self.mock_server = MagicMock()
        self.mock_server_cls.return_value = self.mock_server

        self.video_receiver_patcher = patch("v3xctrl_ui.network.NetworkController.VideoReceiver")
        self.mock_video_receiver_cls = self.video_receiver_patcher.start()
        self.mock_video_receiver = MagicMock()
        self.mock_video_receiver_cls.return_value = self.mock_video_receiver

        self.peer_patcher = patch("v3xctrl_ui.network.NetworkController.Peer")
        self.mock_peer_cls = self.peer_patcher.start()

        self.get_ip_patcher = patch("v3xctrl_ui.network.NetworkController.get_external_ip")
        self.mock_get_ip = self.get_ip_patcher.start()
        self.mock_get_ip.return_value = "192.168.1.100"

        self.socket_patcher = patch("v3xctrl_ui.network.NetworkController.socket")
        self.mock_socket = self.socket_patcher.start()

        self.threading_patcher = patch("v3xctrl_ui.network.NetworkController.threading.Thread")
        self.mock_thread_cls = self.threading_patcher.start()
        self.mock_thread = MagicMock()
        self.mock_thread_cls.return_value = self.mock_thread

    def tearDown(self):
        """Clean up patches."""
        self.server_patcher.stop()
        self.video_receiver_patcher.stop()
        self.peer_patcher.stop()
        self.get_ip_patcher.stop()
        self.socket_patcher.stop()
        self.threading_patcher.stop()

    def test_initialization_relay_disabled(self):
        """Test NetworkManager initialization with relay disabled."""
        with patch('builtins.print') as mock_print:
            nm = NetworkController(self.settings, self.handlers)

            self.assertEqual(nm.video_port, 5000)
            self.assertEqual(nm.control_port, 6000)
            self.assertEqual(nm.settings, self.settings)
            self.assertEqual(nm.server_handlers, self.handlers)

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
            "ports": {"video": 5000, "control": 6000},
            "udp_packet_ttl": 100
        }.get(key, default)

        with patch('builtins.print') as mock_print:
            nm = NetworkController(relay_settings, self.handlers)

            # Relay should be configured
            self.assertTrue(nm.relay_enable)
            self.assertEqual(nm.relay_server, "relay.example.com")
            self.assertEqual(nm.relay_port, 8080)
            self.assertEqual(nm.relay_id, "test123")

            # Should not print connection info when relay is enabled
            mock_print.assert_not_called()

    def test_setup_relay_valid_port(self):
        """Test setup_relay with valid port in server string."""
        nm = NetworkController(self.settings, self.handlers)

        nm.setup_relay("example.com:9999", "testid")

        self.assertTrue(nm.relay_enable)
        self.assertEqual(nm.relay_server, "example.com")
        self.assertEqual(nm.relay_port, 9999)
        self.assertEqual(nm.relay_id, "testid")

    def test_setup_relay_invalid_port(self):
        """Test setup_relay with invalid port in server string."""
        nm = NetworkController(self.settings, self.handlers)

        with patch("v3xctrl_ui.network.NetworkController.logging.warning") as mock_warning:
            nm.setup_relay("example.com:notaport", "testid")

            self.assertTrue(nm.relay_enable)
            self.assertEqual(nm.relay_server, "example.com")
            self.assertEqual(nm.relay_port, 8888)  # Default port
            self.assertEqual(nm.relay_id, "testid")
            mock_warning.assert_called()

    def test_setup_relay_no_port(self):
        """Test setup_relay with no port in server string."""
        nm = NetworkController(self.settings, self.handlers)

        nm.setup_relay("example.com", "testid")

        self.assertTrue(nm.relay_enable)
        self.assertEqual(nm.relay_server, "example.com")
        self.assertEqual(nm.relay_port, 8888)  # Default port
        self.assertEqual(nm.relay_id, "testid")

    def test_setup_ports_no_relay(self):
        """Test setup_ports without relay."""
        nm = NetworkController(self.settings, self.handlers)

        nm.setup_ports()

        # Verify thread was started
        self.mock_thread_cls.assert_called_once()
        self.mock_thread.start.assert_called_once()

        # Execute the task function manually to test it
        task_func = self.mock_thread_cls.call_args[1]['target']
        task_func()

        # Verify video receiver and server were initialized
        self.mock_video_receiver_cls.assert_called_once()

        # Server should be called with messages, states
        self.mock_server_cls.assert_called_once_with(6000, 100)
        self.mock_server.subscribe.assert_called()
        self.mock_server.on.assert_called()
        self.mock_server.start.assert_called_once()

    def test_setup_ports_with_relay_success(self):
        """Test setup_ports with successful relay connection."""
        nm = NetworkController(self.settings, self.handlers)
        nm.setup_relay("relay.example.com:8080", "testid")

        # Mock Peer setup
        mock_peer = MagicMock()
        mock_peer.setup.return_value = {"video": ("1.2.3.4", 1234)}
        self.mock_peer_cls.return_value = mock_peer

        nm.setup_ports()

        # Execute the task function
        task_func = self.mock_thread_cls.call_args[1]['target']
        task_func()

        # Verify peer was set up
        self.mock_peer_cls.assert_called_with("relay.example.com", 8080, "testid")
        mock_peer.setup.assert_called_with("viewer", {"video": 5000, "control": 6000})

    def test_setup_ports_with_relay_registration_error(self):
        """Test setup_ports with peer registration error."""
        nm = NetworkController(self.settings, self.handlers)
        nm.setup_relay("relay.example.com:8080", "badid")

        # Mock Peer to raise PeerRegistrationError
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
        nm = NetworkController(self.settings, self.handlers)

        # Mock Server to raise OSError (port in use)
        self.mock_server_cls.side_effect = OSError(98, "Address already in use")

        with patch("v3xctrl_ui.network.NetworkController.logging.error") as mock_log_error:
            nm.setup_ports()

            # Execute the task function
            task_func = self.mock_thread_cls.call_args[1]['target']
            task_func()

            # Verify error was logged and stored
            self.assertEqual(nm.server_error, "Control port already in use")
            mock_log_error.assert_called_once()

    def test_send_latency_check_with_server(self):
        """Test send_latency_check when server is available."""
        nm = NetworkController(self.settings, self.handlers)

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
        nm = NetworkController(self.settings, self.handlers)

        # No server
        nm.server = None
        nm.server_error = None

        nm.send_latency_check()

        # Should not raise exception, just do nothing

    def test_send_latency_check_with_server_error(self):
        """Test send_latency_check when server has an error."""
        nm = NetworkController(self.settings, self.handlers)

        # Server with error
        mock_server = MagicMock()
        nm.server = mock_server
        nm.server_error = "Connection failed"

        nm.send_latency_check()

        # Should not send when there's an error
        mock_server.send.assert_not_called()

    def test_get_data_queue_size_with_server(self):
        """Test get_data_queue_size when server is available."""
        nm = NetworkController(self.settings, self.handlers)

        # Mock server with queue
        mock_server = MagicMock()
        mock_server.transmitter.queue.qsize.return_value = 42
        nm.server = mock_server
        nm.server_error = None

        result = nm.get_data_queue_size()

        self.assertEqual(result, 42)

    def test_get_data_queue_size_no_server(self):
        """Test get_data_queue_size when no server is available."""
        nm = NetworkController(self.settings, self.handlers)

        # No server
        nm.server = None

        result = nm.get_data_queue_size()

        self.assertEqual(result, 0)

    def test_get_data_queue_size_with_server_error(self):
        """Test get_data_queue_size when server has an error."""
        nm = NetworkController(self.settings, self.handlers)

        # Server with error
        mock_server = MagicMock()
        nm.server = mock_server
        nm.server_error = "Connection failed"

        result = nm.get_data_queue_size()

        self.assertEqual(result, 0)

    def test_update_ttl(self):
        """Test update_ttl method."""
        nm = NetworkController(self.settings, self.handlers)

        # Mock server
        mock_server = MagicMock()
        nm.server = mock_server

        nm.update_ttl(200)

        mock_server.update_ttl.assert_called_once_with(200)

    def test_update_ttl_no_server(self):
        """Test update_ttl when no server exists."""
        nm = NetworkController(self.settings, self.handlers)

        # No server
        nm.server = None

        # Should not raise exception
        nm.update_ttl(200)

    def test_shutdown_with_all_components(self):
        """Test shutdown when all components exist."""
        nm = NetworkController(self.settings, self.handlers)

        # Mock components
        mock_server = MagicMock()
        mock_video_receiver = MagicMock()
        mock_peer = MagicMock()
        nm.server = mock_server
        nm.video_receiver = mock_video_receiver
        nm.peer = mock_peer

        nm.shutdown()

        # Verify shutdown sequence
        mock_server.stop.assert_called_once()
        mock_server.join.assert_called_once()
        mock_peer.abort.assert_called_once()
        mock_video_receiver.stop.assert_called_once()
        mock_video_receiver.join.assert_called_once()

    def test_shutdown_with_no_components(self):
        """Test shutdown when no components exist."""
        nm = NetworkController(self.settings, self.handlers)

        # No components
        nm.server = None
        nm.video_receiver = None
        nm.peer = None

        # Should not raise exception
        nm.shutdown()

    def test_shutdown_partial_components(self):
        """Test shutdown when only some components exist."""
        nm = NetworkController(self.settings, self.handlers)

        # Only server, no video receiver or peer
        mock_server = MagicMock()
        nm.server = mock_server
        nm.video_receiver = None
        nm.peer = None

        nm.shutdown()

        # Only server should be shut down
        mock_server.stop.assert_called_once()
        mock_server.join.assert_called_once()

    def test_initialization_relay_enabled_no_server(self):
        """Test NetworkManager initialization with relay enabled but no server."""
        relay_settings = MagicMock()
        relay_settings.get.side_effect = lambda key, default=None: {
            "relay": {"enabled": True, "id": "test123"},  # Missing server
            "ports": {"video": 5000, "control": 6000},
            "udp_packet_ttl": 100
        }.get(key, default)

        with patch('builtins.print') as mock_print:
            nm = NetworkController(relay_settings, self.handlers)

            # Relay should not be configured due to missing server
            self.assertFalse(nm.relay_enable)
            self.assertIsNone(nm.relay_server)
            self.assertIsNone(nm.relay_id)

    def test_initialization_relay_enabled_no_id(self):
        """Test NetworkManager initialization with relay enabled but no ID."""
        relay_settings = MagicMock()
        relay_settings.get.side_effect = lambda key, default=None: {
            "relay": {"enabled": True, "server": "relay.example.com:8080"},  # Missing ID
            "ports": {"video": 5000, "control": 6000},
            "udp_packet_ttl": 100
        }.get(key, default)

        with patch('builtins.print') as mock_print:
            nm = NetworkController(relay_settings, self.handlers)

            # Relay should not be configured due to missing ID
            self.assertFalse(nm.relay_enable)
            self.assertIsNone(nm.relay_server)
            self.assertIsNone(nm.relay_id)

    def test_setup_relay_empty_server(self):
        """Test setup_relay with empty server string."""
        nm = NetworkController(self.settings, self.handlers)

        nm.setup_relay("", "testid")

        self.assertTrue(nm.relay_enable)
        self.assertEqual(nm.relay_server, "")
        self.assertEqual(nm.relay_port, 8888)  # Default port
        self.assertEqual(nm.relay_id, "testid")


if __name__ == '__main__':
    unittest.main()
