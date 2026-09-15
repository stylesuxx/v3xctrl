import unittest
from collections import deque
from unittest.mock import MagicMock, patch

from tests.v3xctrl_ui.settings_helper import build_settings
from v3xctrl_control.message import Command
from v3xctrl_ui.network.NetworkController import NetworkController
from v3xctrl_ui.network.video.ClockOffset import ClockOffset


class TestNetworkController(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures with proper mocking."""
        self.settings = build_settings(
            relay={"enabled": False},
            ports={"video": 5000, "control": 6000},
            udp_packet_ttl=100,
        )

        # Mock handlers
        self.handlers = {"messages": [("TestMessage", lambda msg, addr: None)], "states": [("CONNECTED", lambda: None)]}

        # Patch external dependencies
        self.server_patcher = patch("v3xctrl_ui.network.NetworkController.Server")
        self.mock_server_cls = self.server_patcher.start()
        self.mock_server = MagicMock()
        self.mock_server_cls.return_value = self.mock_server

        self.mock_video_receiver_cls = MagicMock()
        self.mock_video_receiver = MagicMock()
        self.mock_video_receiver_cls.return_value = self.mock_video_receiver
        self.video_receiver_patcher = patch(
            "v3xctrl_ui.network.NetworkSetup._get_pyav_receiver",
            return_value=self.mock_video_receiver_cls,
        )
        self.video_receiver_patcher.start()

        self.peer_patcher = patch("v3xctrl_relay.Peer.Peer")
        self.mock_peer_cls = self.peer_patcher.start()

        self.network_setup_patcher = patch("v3xctrl_ui.network.NetworkController.NetworkSetup")
        self.mock_network_setup_cls = self.network_setup_patcher.start()
        self.mock_network_setup = MagicMock()
        self.mock_network_setup_cls.return_value = self.mock_network_setup

        self.threading_patcher = patch("v3xctrl_ui.network.NetworkController.threading.Thread")
        self.mock_thread_cls = self.threading_patcher.start()
        self.mock_thread = MagicMock()
        self.mock_thread_cls.return_value = self.mock_thread

        self.clock_offset = ClockOffset()

    def tearDown(self):
        """Clean up patches."""
        self.server_patcher.stop()
        self.video_receiver_patcher.stop()
        self.peer_patcher.stop()
        self.network_setup_patcher.stop()
        self.threading_patcher.stop()

    def test_initialization_relay_disabled(self):
        """Test NetworkController initialization with relay disabled."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        self.assertEqual(nm.video_port, 5000)
        self.assertEqual(nm.control_port, 6000)
        self.assertEqual(nm.settings, self.settings)
        self.assertEqual(nm.server_handlers, self.handlers)

        # Initial state
        self.assertIsNone(nm.video_receiver)
        self.assertIsNone(nm.server)
        self.assertIsNone(nm.get_server_error())
        self.assertFalse(nm.is_relay_enabled())

    def test_initialization_relay_enabled(self):
        """Test NetworkController initialization with relay enabled."""
        relay_settings = build_settings(
            relay={"enabled": True, "server": "relay.example.com:8080", "id": "test123"},
            ports={"video": 5000, "control": 6000},
            udp_packet_ttl=100,
        )

        nm = NetworkController(relay_settings, self.handlers, self.clock_offset)

        # Relay should be configured
        self.assertTrue(nm.is_relay_enabled())
        self.assertEqual(nm.relay_server, "relay.example.com")
        self.assertEqual(nm.relay_port, 8080)
        self.assertEqual(nm.relay_id, "test123")

    def test_setup_relay_valid_port(self):
        """Test setup_relay with valid port in server string."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        nm.setup_relay("example.com:9999", "testid")

        self.assertTrue(nm.is_relay_enabled())
        self.assertEqual(nm.relay_server, "example.com")
        self.assertEqual(nm.relay_port, 9999)
        self.assertEqual(nm.relay_id, "testid")

    def test_setup_relay_invalid_port(self):
        """Test setup_relay with invalid port in server string."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        with patch("v3xctrl_ui.network.NetworkController.logger") as mock_logger:
            nm.setup_relay("example.com:notaport", "testid")

            self.assertTrue(nm.is_relay_enabled())
            self.assertEqual(nm.relay_server, "example.com")
            self.assertEqual(nm.relay_port, 8888)  # Default port
            self.assertEqual(nm.relay_id, "testid")
            mock_logger.warning.assert_called()

    def test_setup_relay_no_port(self):
        """Test setup_relay with no port in server string."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        nm.setup_relay("example.com", "testid")

        self.assertTrue(nm.is_relay_enabled())
        self.assertEqual(nm.relay_server, "example.com")
        self.assertEqual(nm.relay_port, 8888)  # Default port
        self.assertEqual(nm.relay_id, "testid")

    def test_setup_ports_no_relay(self):
        """Test setup_ports without relay."""
        from v3xctrl_ui.network.NetworkSetup import NetworkSetupResult, ServerSetupResult, VideoReceiverSetupResult

        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # Mock NetworkSetup to return successful result
        mock_result = NetworkSetupResult(
            relay_result=None,
            video_receiver_result=VideoReceiverSetupResult(success=True, video_receiver=self.mock_video_receiver),
            server_result=ServerSetupResult(success=True, server=self.mock_server),
        )
        self.mock_network_setup.orchestrate_setup.return_value = mock_result

        nm.setup_ports()

        # Verify thread was started
        self.mock_thread_cls.assert_called_once()
        self.mock_thread.start.assert_called_once()

        # Execute the task function manually to test it
        task_func = self.mock_thread_cls.call_args[1]["target"]
        task_func()

        # Verify NetworkSetup was instantiated and orchestrate_setup was called
        self.mock_network_setup_cls.assert_called_once_with(self.settings)
        self.mock_network_setup.orchestrate_setup.assert_called_once()

        # Verify results were applied
        self.assertEqual(nm.server, self.mock_server)
        self.assertEqual(nm.video_receiver, self.mock_video_receiver)

    def test_setup_ports_with_relay_success(self):
        """Test setup_ports with successful relay connection."""
        from v3xctrl_ui.network.NetworkSetup import (
            NetworkSetupResult,
            RelaySetupResult,
            ServerSetupResult,
            VideoReceiverSetupResult,
        )

        nm = NetworkController(self.settings, self.handlers, self.clock_offset)
        nm.setup_relay("relay.example.com:8080", "testid")

        # Mock NetworkSetup to return successful relay result
        mock_result = NetworkSetupResult(
            relay_result=RelaySetupResult(
                success=True,
                video_address=("1.2.3.4", 1234),
            ),
            video_receiver_result=VideoReceiverSetupResult(success=True, video_receiver=self.mock_video_receiver),
            server_result=ServerSetupResult(success=True, server=self.mock_server),
        )
        self.mock_network_setup.orchestrate_setup.return_value = mock_result

        nm.setup_ports()

        # Execute the task function
        task_func = self.mock_thread_cls.call_args[1]["target"]
        task_func()

        # Verify NetworkSetup orchestration was called with relay config
        call_args = self.mock_network_setup.orchestrate_setup.call_args[0]
        relay_config = call_args[0]
        self.assertIsNotNone(relay_config)
        self.assertEqual(relay_config["server"], "relay.example.com")
        self.assertEqual(relay_config["port"], 8080)
        self.assertEqual(relay_config["id"], "testid")

        # Verify setup instance was stored
        self.assertEqual(nm._setup, self.mock_network_setup)

    def test_setup_ports_with_relay_registration_error(self):
        """Test setup_ports with peer registration error."""
        from v3xctrl_ui.network.NetworkSetup import (
            NetworkSetupResult,
            RelaySetupResult,
            ServerSetupResult,
            VideoReceiverSetupResult,
        )

        nm = NetworkController(self.settings, self.handlers, self.clock_offset)
        nm.setup_relay("relay.example.com:8080", "badid")

        # Mock NetworkSetup to return relay error
        mock_result = NetworkSetupResult(
            relay_result=RelaySetupResult(
                success=False, error_message="Peer registration failed - check server and ID!"
            ),
            video_receiver_result=VideoReceiverSetupResult(success=True, video_receiver=self.mock_video_receiver),
            server_result=ServerSetupResult(success=True, server=self.mock_server),
        )
        self.mock_network_setup.orchestrate_setup.return_value = mock_result

        nm.setup_ports()

        # Execute the task function
        task_func = self.mock_thread_cls.call_args[1]["target"]
        task_func()

        # Verify error message was set
        self.assertIn("registration failed", nm.get_relay_status_message().lower())

    def test_setup_ports_server_error(self):
        """Test setup_ports when server initialization fails."""
        from v3xctrl_ui.network.NetworkSetup import NetworkSetupResult, ServerSetupResult, VideoReceiverSetupResult

        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # Mock NetworkSetup to return server error
        mock_result = NetworkSetupResult(
            relay_result=None,
            video_receiver_result=VideoReceiverSetupResult(success=True, video_receiver=self.mock_video_receiver),
            server_result=ServerSetupResult(success=False, error_message="Control port already in use"),
        )
        self.mock_network_setup.orchestrate_setup.return_value = mock_result

        nm.setup_ports()

        # Execute the task function
        task_func = self.mock_thread_cls.call_args[1]["target"]
        task_func()

        # Verify error was stored
        self.assertEqual(nm.get_server_error(), "Control port already in use")

    def test_send_latency_check_with_server(self):
        """Test send_latency_check when server is available."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # Mock server
        mock_server = MagicMock()
        nm.server = mock_server
        nm._server_error = None

        nm.send_latency_check()

        # Verify Latency message was sent
        mock_server.send.assert_called_once()
        # Check that the argument is a Latency instance
        call_args = mock_server.send.call_args[0]
        self.assertEqual(call_args[0].__class__.__name__, "Latency")

    def test_send_latency_check_no_server(self):
        """Test send_latency_check when no server is available."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # No server
        nm.server = None
        nm._server_error = None

        nm.send_latency_check()

        # Should not raise exception, just do nothing

    def test_send_latency_check_with_server_error(self):
        """Test send_latency_check when server has an error."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # Server with error
        mock_server = MagicMock()
        nm.server = mock_server
        nm._server_error = "Connection failed"

        nm.send_latency_check()

        # Should not send when there's an error
        mock_server.send.assert_not_called()

    def test_get_data_queue_size_with_server(self):
        """Test get_data_queue_size when server is available."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # Mock server with queue
        mock_server = MagicMock()
        mock_server.transmitter.queue.qsize.return_value = 42
        nm.server = mock_server
        nm._server_error = None

        result = nm.get_data_queue_size()

        self.assertEqual(result, 42)

    def test_get_data_queue_size_no_server(self):
        """Test get_data_queue_size when no server is available."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # No server
        nm.server = None

        result = nm.get_data_queue_size()

        self.assertEqual(result, 0)

    def test_get_data_queue_size_with_server_error(self):
        """Test get_data_queue_size when server has an error."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # Server with error
        mock_server = MagicMock()
        nm.server = mock_server
        nm._server_error = "Connection failed"

        result = nm.get_data_queue_size()

        self.assertEqual(result, 0)

    def test_update_ttl(self):
        """Test update_ttl method."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # Mock server
        mock_server = MagicMock()
        nm.server = mock_server

        nm.update_ttl(200)

        mock_server.update_ttl.assert_called_once_with(200)

    def test_update_ttl_no_server(self):
        """Test update_ttl when no server exists."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # No server
        nm.server = None

        # Should not raise exception
        nm.update_ttl(200)

    def test_shutdown_with_all_components(self):
        """Test shutdown when all components exist."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # Mock components
        mock_server = MagicMock()
        mock_video_receiver = MagicMock()
        mock_setup = MagicMock()
        nm.server = mock_server
        nm.video_receiver = mock_video_receiver
        nm._setup = mock_setup

        nm.shutdown()

        # Verify shutdown sequence
        mock_setup.abort.assert_called_once()
        mock_server.stop.assert_called_once()
        mock_server.join.assert_called_once()
        mock_video_receiver.stop.assert_called_once()
        mock_video_receiver.join.assert_called_once()

    def test_shutdown_with_no_components(self):
        """Test shutdown when no components exist."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # No components
        nm.server = None
        nm.video_receiver = None
        nm._setup = None

        # Should not raise exception
        nm.shutdown()

    def test_shutdown_partial_components(self):
        """Test shutdown when only some components exist."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        # Only server, no video receiver or setup
        mock_server = MagicMock()
        nm.server = mock_server
        nm.video_receiver = None
        nm._setup = None

        nm.shutdown()

        # Only server should be shut down
        mock_server.stop.assert_called_once()
        mock_server.join.assert_called_once()

    def test_initialization_relay_enabled_no_server(self):
        """Test NetworkController initialization with relay enabled but no server."""
        relay_settings = build_settings(
            relay={"enabled": True, "id": "test123", "server": ""},  # Missing server
            ports={"video": 5000, "control": 6000},
            udp_packet_ttl=100,
        )

        nm = NetworkController(relay_settings, self.handlers, self.clock_offset)

        # Relay should not be configured due to missing server
        self.assertFalse(nm.is_relay_enabled())
        self.assertIsNone(nm.relay_server)
        self.assertIsNone(nm.relay_id)

    def test_initialization_relay_enabled_no_id(self):
        """Test NetworkController initialization with relay enabled but no ID."""
        relay_settings = build_settings(
            relay={"enabled": True, "server": "relay.example.com:8080", "id": ""},  # Missing ID
            ports={"video": 5000, "control": 6000},
            udp_packet_ttl=100,
        )

        nm = NetworkController(relay_settings, self.handlers, self.clock_offset)

        # Relay should not be configured due to missing ID
        self.assertFalse(nm.is_relay_enabled())
        self.assertIsNone(nm.relay_server)
        self.assertIsNone(nm.relay_id)

    def test_setup_relay_empty_server(self):
        """Test setup_relay with empty server string."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        nm.setup_relay("", "testid")

        self.assertTrue(nm.is_relay_enabled())
        self.assertEqual(nm.relay_server, "")
        self.assertEqual(nm.relay_port, 8888)  # Default port
        self.assertEqual(nm.relay_id, "testid")

    def test_get_control_buffer_size_with_server(self):
        """Test get_control_buffer_size when server is available."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        mock_server = MagicMock()
        mock_server.transmitter.get_control_buffer_size.return_value = 3
        nm.server = mock_server
        nm._server_error = None

        result = nm.get_control_buffer_size()

        self.assertEqual(result, 3)

    def test_get_control_buffer_size_no_server(self):
        """Test get_control_buffer_size when no server is available."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)
        nm.server = None

        result = nm.get_control_buffer_size()

        self.assertEqual(result, 0)

    def test_get_control_buffer_size_with_server_error(self):
        """Test get_control_buffer_size when server has an error."""
        nm = NetworkController(self.settings, self.handlers, self.clock_offset)

        mock_server = MagicMock()
        nm.server = mock_server
        nm._server_error = "Connection failed"

        result = nm.get_control_buffer_size()

        self.assertEqual(result, 0)


class TestChannelOperations(unittest.TestCase):
    """The guards that used to live in NetworkCoordinator, now where the state is."""

    def setUp(self):
        self.settings = build_settings(relay={"enabled": False}, ports={"video": 5000, "control": 6000})
        self.handlers = {"messages": [], "states": []}
        self.clock_offset = ClockOffset()

    def _controller(self) -> NetworkController:
        return NetworkController(self.settings, self.handlers, self.clock_offset)

    def test_control_is_sent_when_the_channel_is_up(self):
        controller = self._controller()
        controller.server = MagicMock()
        controller._server_error = None

        controller.send_control(0.5, -0.3)

        sent = controller.server.send_control.call_args[0][0]
        self.assertEqual(sent.values, {"steering": -0.3, "throttle": 0.5})

    def test_control_is_dropped_without_a_server(self):
        controller = self._controller()
        controller.server = None

        controller.send_control(0.5, -0.3)

    def test_control_is_dropped_while_the_server_is_in_error(self):
        controller = self._controller()
        controller.server = MagicMock()
        controller._server_error = "Control port already in use"

        controller.send_control(0.5, -0.3)

        controller.server.send_control.assert_not_called()

    def test_send_command_reports_whether_it_could_send(self):
        controller = self._controller()
        callback = MagicMock()

        controller.server = None
        self.assertFalse(controller.send_command(Command({"action": "test"}), callback))

        controller.server = MagicMock()
        self.assertTrue(controller.send_command(Command({"action": "test"}), callback))
        controller.server.send_command.assert_called_once()

    def test_video_reads_fall_back_without_a_receiver(self):
        controller = self._controller()
        controller.video_receiver = None

        self.assertIsNone(controller.get_video_frame())
        self.assertIsNone(controller.get_video_history())
        self.assertEqual(controller.get_video_buffer_size(), 0)

    def test_video_reads_go_to_the_receiver(self):
        controller = self._controller()
        receiver = MagicMock()
        receiver.frame_buffer = [1, 2, 3]
        receiver.render_history = deque([1.0, 2.0])
        controller.video_receiver = receiver

        self.assertIs(controller.get_video_frame(), receiver.get_frame.return_value)
        self.assertEqual(controller.get_video_history(), deque([1.0, 2.0]))
        self.assertEqual(controller.get_video_buffer_size(), 3)

    def test_the_video_history_handed_out_is_a_copy(self):
        """The render path must not be able to mutate the receiver's history."""
        controller = self._controller()
        receiver = MagicMock()
        receiver.render_history = deque([1.0])
        controller.video_receiver = receiver

        controller.get_video_history().append(2.0)

        self.assertEqual(receiver.render_history, deque([1.0]))

    def test_transmitter_health_falls_back_without_a_server(self):
        controller = self._controller()
        controller.server = None

        self.assertFalse(controller.has_recent_control_drops())
        self.assertFalse(controller.has_recent_send_failures())

    def test_transmitter_health_falls_back_while_the_server_is_in_error(self):
        controller = self._controller()
        controller.server = MagicMock()
        controller._server_error = "Control port already in use"

        self.assertFalse(controller.has_recent_control_drops())
        self.assertFalse(controller.has_recent_send_failures())


if __name__ == "__main__":
    unittest.main()
