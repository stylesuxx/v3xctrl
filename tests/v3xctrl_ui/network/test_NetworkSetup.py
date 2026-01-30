import unittest
from unittest.mock import MagicMock, patch, call

from v3xctrl_helper.exceptions import PeerRegistrationError
from v3xctrl_ui.network.NetworkSetup import (
    NetworkSetup,
    RelaySetupResult,
    VideoReceiverSetupResult,
    ServerSetupResult,
    NetworkSetupResult
)


class TestNetworkSetup(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Mock settings
        self.settings = MagicMock()
        self.settings.get.side_effect = lambda key, default=None: {
            "ports": {"video": 5000, "control": 6000},
            "udp_packet_ttl": 100,
            "video": {"render_ratio": 0}
        }.get(key, default)

        # Patch external dependencies
        self.peer_patcher = patch("v3xctrl_ui.network.NetworkSetup.Peer")
        self.mock_peer_cls = self.peer_patcher.start()

        self.server_patcher = patch("v3xctrl_ui.network.NetworkSetup.Server")
        self.mock_server_cls = self.server_patcher.start()

        self.video_receiver_patcher = patch("v3xctrl_ui.network.NetworkSetup.VideoReceiver")
        self.mock_video_receiver_cls = self.video_receiver_patcher.start()

        self.socket_patcher = patch("v3xctrl_ui.network.NetworkSetup.socket")
        self.mock_socket = self.socket_patcher.start()

    def tearDown(self):
        """Clean up patches."""
        self.peer_patcher.stop()
        self.server_patcher.stop()
        self.video_receiver_patcher.stop()
        self.socket_patcher.stop()

    def test_setup_relay_success(self):
        """Test successful relay setup."""
        setup = NetworkSetup(self.settings)

        # Mock peer setup
        mock_peer = MagicMock()
        mock_peer.setup.return_value = {"video": ("1.2.3.4", 1234)}
        self.mock_peer_cls.return_value = mock_peer

        result = setup.setup_relay("relay.example.com", 8080, "test123")

        # Verify successful result
        self.assertTrue(result.success)
        self.assertEqual(result.video_address, ("1.2.3.4", 1234))
        self.assertIsNone(result.error_message)

        # Verify peer was stored internally
        self.assertEqual(setup._peer, mock_peer)

        # Verify peer was called correctly
        self.mock_peer_cls.assert_called_once_with("relay.example.com", 8080, "test123")
        mock_peer.setup.assert_called_once_with(
            "viewer",
            {"video": 5000, "control": 6000}
        )

    def test_setup_relay_registration_error(self):
        """Test relay setup with registration error."""
        setup = NetworkSetup(self.settings)

        # Mock peer to raise PeerRegistrationError
        mock_peer = MagicMock()
        mock_peer.setup.side_effect = PeerRegistrationError({}, {})
        self.mock_peer_cls.return_value = mock_peer

        result = setup.setup_relay("relay.example.com", 8080, "badid")

        # Verify error result
        self.assertFalse(result.success)
        self.assertIsNone(result.video_address)
        self.assertIn("registration failed", result.error_message.lower())

    def test_create_keep_alive_callback_with_address(self):
        """Test creating keep-alive callback with video address."""
        setup = NetworkSetup(self.settings)

        # Mock socket
        mock_sock_instance = MagicMock()
        self.mock_socket.socket.return_value = mock_sock_instance

        callback = setup.create_keep_alive_callback(("1.2.3.4", 1234))

        # Execute callback
        callback()

        # Verify socket operations
        self.mock_socket.socket.assert_called_once()
        mock_sock_instance.bind.assert_called_once_with(("0.0.0.0", 5000))

        # Verify sendto was called 3 times (retries = 3)
        self.assertEqual(mock_sock_instance.sendto.call_count, 3)
        for call_args in mock_sock_instance.sendto.call_args_list:
            # Verify Heartbeat message is sent (msgpack encoded)
            self.assertIsInstance(call_args[0][0], bytes)
            self.assertEqual(call_args[0][1], ("1.2.3.4", 1234))

        mock_sock_instance.close.assert_called_once()

    def test_create_keep_alive_callback_without_address(self):
        """Test creating keep-alive callback without video address."""
        setup = NetworkSetup(self.settings)

        callback = setup.create_keep_alive_callback(None)

        # Execute callback - should be no-op
        callback()

        # Verify no socket operations
        self.mock_socket.socket.assert_not_called()

    def test_setup_video_receiver_success(self):
        """Test successful video receiver setup."""
        setup = NetworkSetup(self.settings)

        mock_receiver = MagicMock()
        self.mock_video_receiver_cls.return_value = mock_receiver

        error_callback = MagicMock()
        result = setup.setup_video_receiver(error_callback)

        # Verify successful result
        self.assertTrue(result.success)
        self.assertEqual(result.video_receiver, mock_receiver)
        self.assertIsNone(result.error)

        # Verify receiver was created and started
        self.mock_video_receiver_cls.assert_called_once_with(
            5000,
            error_callback,
            render_ratio=0
        )
        mock_receiver.start.assert_called_once()

    def test_setup_video_receiver_error(self):
        """Test video receiver setup with error."""
        setup = NetworkSetup(self.settings)

        # Mock receiver to raise exception on start
        mock_receiver = MagicMock()
        test_exception = RuntimeError("Video receiver failed")
        mock_receiver.start.side_effect = test_exception
        self.mock_video_receiver_cls.return_value = mock_receiver

        error_callback = MagicMock()
        result = setup.setup_video_receiver(error_callback)

        # Verify error result
        self.assertFalse(result.success)
        self.assertIsNone(result.video_receiver)
        self.assertEqual(result.error, test_exception)

    def test_setup_server_success(self):
        """Test successful server setup."""
        setup = NetworkSetup(self.settings)

        mock_server = MagicMock()
        self.mock_server_cls.return_value = mock_server

        message_handlers = [("TestMessage", lambda m, a: None)]
        state_handlers = [("CONNECTED", lambda: None)]

        result = setup.setup_server(message_handlers, state_handlers)

        # Verify successful result
        self.assertTrue(result.success)
        self.assertEqual(result.server, mock_server)
        self.assertIsNone(result.error_message)

        # Verify server was created correctly
        self.mock_server_cls.assert_called_once_with(6000, 100)
        mock_server.subscribe.assert_called_once()
        mock_server.on.assert_called_once()
        mock_server.start.assert_called_once()

    def test_setup_server_port_in_use_error(self):
        """Test server setup when port is already in use."""
        setup = NetworkSetup(self.settings)

        # Mock server to raise OSError with errno 98 (port in use)
        self.mock_server_cls.side_effect = OSError(98, "Address already in use")

        message_handlers = []
        state_handlers = []

        result = setup.setup_server(message_handlers, state_handlers)

        # Verify error result
        self.assertFalse(result.success)
        self.assertIsNone(result.server)
        self.assertEqual(result.error_message, "Control port already in use")

    def test_setup_server_other_error(self):
        """Test server setup with other OSError."""
        setup = NetworkSetup(self.settings)

        # Mock server to raise OSError with different errno
        self.mock_server_cls.side_effect = OSError(99, "Some other error")

        message_handlers = []
        state_handlers = []

        result = setup.setup_server(message_handlers, state_handlers)

        # Verify error result
        self.assertFalse(result.success)
        self.assertIsNone(result.server)
        self.assertIn("Server error", result.error_message)

    def test_orchestrate_setup_no_relay(self):
        """Test complete setup orchestration without relay."""
        setup = NetworkSetup(self.settings)

        # Mock successful setup
        mock_server = MagicMock()
        mock_receiver = MagicMock()
        self.mock_server_cls.return_value = mock_server
        self.mock_video_receiver_cls.return_value = mock_receiver

        handlers = {
            "messages": [("TestMessage", lambda m, a: None)],
            "states": [("CONNECTED", lambda: None)]
        }

        result = setup.orchestrate_setup(None, handlers)

        # Verify no relay result
        self.assertIsNone(result.relay_result)

        # Verify video receiver success
        self.assertIsNotNone(result.video_receiver_result)
        self.assertTrue(result.video_receiver_result.success)
        self.assertEqual(result.video_receiver_result.video_receiver, mock_receiver)

        # Verify server success
        self.assertIsNotNone(result.server_result)
        self.assertTrue(result.server_result.success)
        self.assertEqual(result.server_result.server, mock_server)

        # Verify no errors
        self.assertFalse(result.has_errors)

    def test_abort_with_peer(self):
        """Test abort() when peer exists."""
        setup = NetworkSetup(self.settings)

        # Mock peer
        mock_peer = MagicMock()
        setup._peer = mock_peer

        setup.abort()

        mock_peer.abort.assert_called_once()

    def test_abort_without_peer(self):
        """Test abort() when no peer exists."""
        setup = NetworkSetup(self.settings)

        # No peer set
        self.assertIsNone(setup._peer)

        # Should not raise exception
        setup.abort()

    def test_orchestrate_setup_with_relay(self):
        """Test complete setup orchestration with relay."""
        setup = NetworkSetup(self.settings)

        # Mock successful relay, receiver, and server setup
        mock_peer = MagicMock()
        mock_peer.setup.return_value = {"video": ("1.2.3.4", 1234)}
        self.mock_peer_cls.return_value = mock_peer

        mock_server = MagicMock()
        mock_receiver = MagicMock()
        self.mock_server_cls.return_value = mock_server
        self.mock_video_receiver_cls.return_value = mock_receiver

        relay_config = {
            'server': 'relay.example.com',
            'port': 8080,
            'id': 'test123'
        }
        handlers = {
            "messages": [],
            "states": []
        }

        result = setup.orchestrate_setup(relay_config, handlers)

        # Verify relay result
        self.assertIsNotNone(result.relay_result)
        self.assertTrue(result.relay_result.success)
        self.assertEqual(result.relay_result.video_address, ("1.2.3.4", 1234))

        # Verify peer was stored internally
        self.assertEqual(setup._peer, mock_peer)

        # Verify video receiver success
        self.assertTrue(result.video_receiver_result.success)

        # Verify server success
        self.assertTrue(result.server_result.success)

        # Verify no errors
        self.assertFalse(result.has_errors)

    def test_orchestrate_setup_with_errors(self):
        """Test setup orchestration when some steps fail."""
        setup = NetworkSetup(self.settings)

        # Mock server error
        self.mock_server_cls.side_effect = OSError(98, "Address already in use")

        # Mock successful video receiver
        mock_receiver = MagicMock()
        self.mock_video_receiver_cls.return_value = mock_receiver

        handlers = {
            "messages": [],
            "states": []
        }

        result = setup.orchestrate_setup(None, handlers)

        # Verify video receiver success
        self.assertTrue(result.video_receiver_result.success)

        # Verify server error
        self.assertFalse(result.server_result.success)
        self.assertEqual(result.server_result.error_message, "Control port already in use")

        # Verify has_errors is True
        self.assertTrue(result.has_errors)

    def test_network_setup_result_has_errors_property(self):
        """Test NetworkSetupResult.has_errors property."""
        # All successful
        result = NetworkSetupResult(
            relay_result=RelaySetupResult(success=True, video_address=("1.2.3.4", 1234)),
            video_receiver_result=VideoReceiverSetupResult(success=True),
            server_result=ServerSetupResult(success=True)
        )
        self.assertFalse(result.has_errors)

        # Relay failed
        result = NetworkSetupResult(
            relay_result=RelaySetupResult(success=False, error_message="Failed"),
            video_receiver_result=VideoReceiverSetupResult(success=True),
            server_result=ServerSetupResult(success=True)
        )
        self.assertTrue(result.has_errors)

        # Server failed
        result = NetworkSetupResult(
            relay_result=None,
            video_receiver_result=VideoReceiverSetupResult(success=True),
            server_result=ServerSetupResult(success=False, error_message="Failed")
        )
        self.assertTrue(result.has_errors)

    def test_setup_relay_port_in_use_error(self):
        """Test relay setup when port is already in use."""
        setup = NetworkSetup(self.settings)

        mock_peer = MagicMock()
        mock_peer.setup.side_effect = OSError(98, "Address already in use")
        self.mock_peer_cls.return_value = mock_peer

        result = setup.setup_relay("relay.example.com", 8080, "test123")

        self.assertFalse(result.success)
        self.assertIsNone(result.video_address)
        self.assertIn("Port already in use", result.error_message)

    def test_setup_relay_other_os_error(self):
        """Test relay setup with a non-EADDRINUSE OSError."""
        setup = NetworkSetup(self.settings)

        mock_peer = MagicMock()
        mock_peer.setup.side_effect = OSError(101, "Network is unreachable")
        self.mock_peer_cls.return_value = mock_peer

        result = setup.setup_relay("relay.example.com", 8080, "test123")

        self.assertFalse(result.success)
        self.assertIsNone(result.video_address)
        self.assertIn("Network error", result.error_message)

    def test_orchestrate_setup_relay_failure_returns_early(self):
        """Test that orchestrate_setup returns early when relay fails."""
        setup = NetworkSetup(self.settings)

        # Mock peer to raise PeerRegistrationError
        mock_peer = MagicMock()
        mock_peer.setup.side_effect = PeerRegistrationError({}, {})
        self.mock_peer_cls.return_value = mock_peer

        relay_config = {
            'server': 'relay.example.com',
            'port': 8080,
            'id': 'badid'
        }
        handlers = {
            "messages": [],
            "states": []
        }

        result = setup.orchestrate_setup(relay_config, handlers)

        # Verify relay failed
        self.assertIsNotNone(result.relay_result)
        self.assertFalse(result.relay_result.success)

        # Verify video receiver and server were NOT started (early return)
        self.assertIsNone(result.video_receiver_result)
        self.assertIsNone(result.server_result)

        # Verify has_errors is True
        self.assertTrue(result.has_errors)


if __name__ == '__main__':
    unittest.main()
