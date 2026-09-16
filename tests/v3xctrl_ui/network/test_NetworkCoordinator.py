import threading
import unittest
from unittest.mock import MagicMock, patch

from tests.v3xctrl_ui.settings_helper import build_settings
from v3xctrl_control import State
from v3xctrl_control.message import Command, Latency, Telemetry
from v3xctrl_ui.core.dataclasses import ApplicationModel
from v3xctrl_ui.core.MainThreadDispatcher import MainThreadDispatcher
from v3xctrl_ui.network.NetworkController import NetworkController
from v3xctrl_ui.network.NetworkCoordinator import NetworkCoordinator


class TestNetworkCoordinator(unittest.TestCase):
    """Test suite for NetworkCoordinator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.model = ApplicationModel(fullscreen=False, throttle=0.0, steering=0.0)
        self.mock_osd = MagicMock()
        self.mock_telemetry_sink = MagicMock()
        self.settings = build_settings(ports={"video": 6666, "control": 6668})
        self.main_thread_dispatcher = MainThreadDispatcher()
        self.coordinator = NetworkCoordinator(
            self.model, self.mock_osd, self.mock_telemetry_sink, self.settings, self.main_thread_dispatcher
        )

    def test_initialization(self):
        """Test NetworkCoordinator initialization."""
        self.assertEqual(self.coordinator.model, self.model)
        self.assertEqual(self.coordinator.osd, self.mock_osd)
        self.assertIsInstance(self.coordinator.network_controller, NetworkController)
        self.assertIsInstance(self.coordinator.restart_complete, threading.Event)
        self.assertIsNone(self.coordinator.on_connection_change)

    @patch("v3xctrl_ui.network.NetworkCoordinator.NetworkController")
    def test_create_network_controller(self, mock_nm_class):
        """Test creating a network controller."""
        mock_nm = MagicMock()
        mock_nm_class.return_value = mock_nm

        result = self.coordinator._create_network_controller(self.settings)

        self.assertEqual(result, mock_nm)
        mock_nm_class.assert_called_once()

        # Verify handlers were created
        call_args = mock_nm_class.call_args
        self.assertEqual(call_args[0][0], self.settings)
        handlers = call_args[0][1]
        self.assertIn("messages", handlers)
        self.assertIn("states", handlers)

    def test_setup_ports(self):
        """Test setting up network ports."""
        mock_nm = MagicMock()
        self.coordinator.network_controller = mock_nm

        self.coordinator.setup_ports()

        mock_nm.setup_ports.assert_called_once()

    @patch("v3xctrl_ui.network.NetworkCoordinator.NetworkController")
    def test_restart_network_controller(self, mock_nm_class):
        """Test restarting network manager in background thread."""
        mock_nm_old = MagicMock()
        mock_nm_new = MagicMock()
        self.coordinator.network_controller = mock_nm_old

        # Set up the mock to return new network manager on second call
        mock_nm_class.return_value = mock_nm_new

        thread = self.coordinator._restart_network_controller(self.settings)

        self.assertIsInstance(thread, threading.Thread)
        self.assertFalse(self.coordinator.restart_complete.is_set())

        # Run the thread
        thread.start()
        thread.join(timeout=1.0)

        # Verify restart completed
        self.assertTrue(self.coordinator.restart_complete.is_set())
        mock_nm_old.shutdown.assert_called_once()

    def test_send_control_message(self):
        """The coordinator forwards control to the channel; the channel builds the message."""
        mock_nm = MagicMock()
        mock_nm.is_spectator.return_value = False
        self.coordinator.network_controller = mock_nm

        self.coordinator.send_control_message(0.5, -0.3)

        mock_nm.send_control.assert_called_once_with(0.5, -0.3)

    def test_send_control_message_no_server(self):
        """Test sending control message when server is None."""
        mock_nm = MagicMock()
        mock_nm.server = None
        self.coordinator.network_controller = mock_nm

        # Should not raise an error
        self.coordinator.send_control_message(0.5, -0.3)

    def test_send_control_message_server_error(self):
        """Test sending control message when server has error."""
        mock_server = MagicMock()
        mock_nm = MagicMock()
        mock_nm.server = mock_server
        mock_nm.get_server_error.return_value = True
        self.coordinator.network_controller = mock_nm

        self.coordinator.send_control_message(0.5, -0.3)

        # Should not send when server has error
        mock_server.send.assert_not_called()

    def test_send_command(self):
        """Test sending a command to the server."""
        mock_nm = MagicMock()
        mock_nm.is_spectator.return_value = False
        mock_nm.send_command.return_value = True
        self.coordinator.network_controller = mock_nm

        command = Command({"action": "test"})
        callback = MagicMock()

        self.coordinator.send_command(command, callback)

        # Verify send_command was called with the command and a deferred callback wrapper
        mock_nm.send_command.assert_called_once()
        call_args = mock_nm.send_command.call_args
        self.assertEqual(call_args[0][0], command)
        # The second arg should be the deferred callback wrapper (a callable)
        self.assertTrue(callable(call_args[0][1]))

        # Simulate the server invoking the deferred callback with success
        deferred_callback = call_args[0][1]
        deferred_callback(True)

        # Draining is what puts the callback on the main thread
        self.main_thread_dispatcher.drain()
        callback.assert_called_once_with(True)

    def test_send_command_is_logged(self):
        mock_nm = MagicMock()
        mock_nm.is_spectator.return_value = False
        mock_nm.send_command.return_value = True
        self.coordinator.network_controller = mock_nm

        with self.assertLogs("v3xctrl_ui.network.NetworkCoordinator", level="INFO") as logs:
            self.coordinator.send_command(Command("trim", {"action": "increase"}), MagicMock())

        self.assertEqual(
            logs.output, ["INFO:v3xctrl_ui.network.NetworkCoordinator:Sending command: trim {'action': 'increase'}"]
        )

    def test_send_command_no_server(self):
        """A channel that reports it could not send makes the callback fire with False."""
        mock_nm = MagicMock()
        mock_nm.send_command.return_value = False
        mock_nm.is_spectator.return_value = False
        self.coordinator.network_controller = mock_nm

        command = Command({"action": "test"})
        callback = MagicMock()

        self.coordinator.send_command(command, callback)

        # Callback should be invoked with False to indicate failure
        callback.assert_called_once_with(False)

    def test_send_latency_check(self):
        """Test sending latency check."""
        mock_nm = MagicMock()
        mock_nm.is_spectator.return_value = False
        self.coordinator.network_controller = mock_nm

        self.coordinator.send_latency_check()

        mock_nm.send_latency_check.assert_called_once()

    def test_update_ttl(self):
        """Test updating UDP TTL."""
        mock_nm = MagicMock()
        self.coordinator.network_controller = mock_nm

        self.coordinator.update_ttl(150)

        mock_nm.update_ttl.assert_called_once_with(150)

    def test_get_video_buffer_size(self):
        """Test getting video buffer size."""
        mock_nm = MagicMock()
        mock_nm.get_video_buffer_size.return_value = 5
        self.coordinator.network_controller = mock_nm

        result = self.coordinator.get_video_buffer_size()

        self.assertEqual(result, 5)

    def test_is_control_connected(self):
        """Test checking control connection status."""
        self.model.control_connected = True

        result = self.coordinator.is_control_connected()

        self.assertTrue(result)

    def test_shutdown(self):
        """Test shutting down network manager."""
        mock_nm = MagicMock()
        self.coordinator.network_controller = mock_nm

        self.coordinator.shutdown()

        mock_nm.shutdown.assert_called_once()

    def test_create_handlers_structure(self):
        """Test that handlers are created with correct structure."""
        handlers = self.coordinator._create_handlers()

        self.assertIn("messages", handlers)
        self.assertIn("states", handlers)

        # Verify message handlers
        messages = handlers["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0][0], Telemetry)
        self.assertEqual(messages[1][0], Latency)

        # Verify state handlers (updated for SPECTATING state)
        states = handlers["states"]
        self.assertEqual(len(states), 6)
        self.assertEqual(states[0][0], State.CONNECTED)
        self.assertEqual(states[1][0], State.SPECTATING)
        self.assertEqual(states[2][0], State.DISCONNECTED)
        self.assertEqual(states[3][0], State.CONNECTED)
        self.assertEqual(states[4][0], State.SPECTATING)
        self.assertEqual(states[5][0], State.DISCONNECTED)

    def test_handlers_update_connected_state(self):
        """Test that handlers update connection state correctly."""
        handlers = self.coordinator._create_handlers()

        # Get the connected and disconnected state handlers (updated indices for SPECTATING state)
        connected_handler = handlers["states"][3][1]
        disconnected_handler = handlers["states"][5][1]

        # Test connected
        self.assertFalse(self.model.control_connected)
        connected_handler()
        self.assertTrue(self.model.control_connected)

        # Test disconnected
        disconnected_handler()
        self.assertFalse(self.model.control_connected)

    def test_state_handlers_log_the_transition(self):
        handlers = self.coordinator._create_handlers()
        connect_handler = handlers["states"][0][1]
        spectate_handler = handlers["states"][1][1]
        disconnect_handler = handlers["states"][2][1]

        with self.assertLogs("v3xctrl_ui.network.NetworkCoordinator", level="INFO") as logs:
            connect_handler()
            disconnect_handler()
            spectate_handler()

        self.assertEqual(
            logs.output,
            [
                "INFO:v3xctrl_ui.network.NetworkCoordinator:Control channel connected",
                "INFO:v3xctrl_ui.network.NetworkCoordinator:Control channel disconnected",
                "INFO:v3xctrl_ui.network.NetworkCoordinator:Control channel connected",
            ],
        )

    def test_handlers_route_to_the_osd_and_the_sink(self):
        """Telemetry lands in the sink; connection state lands in the OSD."""
        handlers = self.coordinator._create_handlers()

        # Test message handlers
        telemetry_handler = handlers["messages"][0][1]
        latency_handler = handlers["messages"][1][1]

        mock_telemetry = MagicMock(spec=Telemetry)
        latency_message = Latency()

        telemetry_handler(mock_telemetry, "address")
        latency_handler(latency_message, "address")

        self.assertEqual(self.mock_telemetry_sink.handle_message.call_count, 2)

        # Test state handlers (both CONNECTED and SPECTATING call connect_handler)
        connect_handler = handlers["states"][0][1]
        spectating_handler = handlers["states"][1][1]
        disconnect_handler = handlers["states"][2][1]

        connect_handler()
        spectating_handler()
        disconnect_handler()

        # The sink is built for the receive thread; the OSD waits for the main loop
        self.mock_telemetry_sink.reset.assert_called_once()
        self.mock_osd.connect_handler.assert_not_called()
        self.mock_osd.disconnect_handler.assert_not_called()

        self.main_thread_dispatcher.drain()

        self.assertEqual(self.mock_osd.connect_handler.call_count, 2)  # Called by both CONNECTED and SPECTATING
        self.mock_osd.disconnect_handler.assert_called_once()

    def test_connection_change_callback(self):
        """Test that connection change callback is invoked."""
        mock_callback = MagicMock()
        self.coordinator.on_connection_change = mock_callback

        handlers = self.coordinator._create_handlers()

        # Get connection state handlers (updated indices for SPECTATING state)
        connected_handler = handlers["states"][3][1]
        disconnected_handler = handlers["states"][5][1]

        # The callback reaches the menu, so it waits for the main loop
        connected_handler()
        mock_callback.assert_not_called()
        self.main_thread_dispatcher.drain()
        mock_callback.assert_called_with(True)

        disconnected_handler()
        self.main_thread_dispatcher.drain()
        mock_callback.assert_called_with(False)

        self.assertEqual(mock_callback.call_count, 2)

    def test_connection_change_callback_not_set(self):
        """Test that missing callback doesn't cause errors."""
        self.coordinator.on_connection_change = None

        handlers = self.coordinator._create_handlers()
        connected_handler = handlers["states"][3][1]  # Updated index for SPECTATING state

        # Should not raise an error
        connected_handler()
        self.assertTrue(self.model.control_connected)

    def test_is_spectator_true(self):
        """Test checking spectator mode when enabled."""
        mock_nm = MagicMock()
        mock_nm.is_spectator.return_value = True
        self.coordinator.network_controller = mock_nm

        result = self.coordinator.is_spectator()

        self.assertTrue(result)

    def test_is_spectator_false(self):
        """Test checking spectator mode when disabled."""
        mock_nm = MagicMock()
        mock_nm.is_spectator.return_value = False
        self.coordinator.network_controller = mock_nm

        result = self.coordinator.is_spectator()

        self.assertFalse(result)

    def test_send_control_message_spectator_mode(self):
        """Test that control messages are not sent in spectator mode."""
        mock_server = MagicMock()
        mock_nm = MagicMock()
        mock_nm.server = mock_server
        mock_nm.get_server_error.return_value = False
        mock_nm.is_spectator.return_value = True
        self.coordinator.network_controller = mock_nm

        self.coordinator.send_control_message(0.5, -0.3)

        # Should not send when in spectator mode
        mock_server.send.assert_not_called()

    def test_send_latency_check_spectator_mode(self):
        """Test that latency checks are not sent in spectator mode."""
        mock_nm = MagicMock()
        mock_nm.is_spectator.return_value = True
        self.coordinator.network_controller = mock_nm

        self.coordinator.send_latency_check()

        # Should not send when in spectator mode
        mock_nm.send_latency_check.assert_not_called()

    def test_get_control_buffer_size(self):
        """Test getting control buffer size."""
        mock_nm = MagicMock()
        mock_nm.get_control_buffer_size.return_value = 3
        self.coordinator.network_controller = mock_nm

        result = self.coordinator.get_control_buffer_size()

        self.assertEqual(result, 3)

    def test_has_recent_send_failures(self):
        """Test checking for recent send failures."""
        mock_nm = MagicMock()
        mock_nm.server = MagicMock()
        mock_nm.get_server_error.return_value = None
        mock_nm.server.transmitter.has_recent_send_failures.return_value = True
        self.coordinator.network_controller = mock_nm

        result = self.coordinator.has_recent_send_failures()

        self.assertTrue(result)

    def test_send_command_spectator_mode(self):
        """Test that commands are not sent in spectator mode."""
        mock_server = MagicMock()
        mock_nm = MagicMock()
        mock_nm.server = mock_server
        mock_nm.is_spectator.return_value = True
        self.coordinator.network_controller = mock_nm

        command = Command({"action": "test"})
        callback = MagicMock()

        self.coordinator.send_command(command, callback)

        # Should not send command when in spectator mode
        mock_server.send_command.assert_not_called()
        # Callback is posted, draining invokes it with False
        self.main_thread_dispatcher.drain()
        callback.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
