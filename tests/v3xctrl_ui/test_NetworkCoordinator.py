import unittest
from unittest.mock import MagicMock, patch
import threading

from src.v3xctrl_ui.NetworkCoordinator import NetworkCoordinator
from src.v3xctrl_ui.ApplicationModel import ApplicationModel
from v3xctrl_control import State
from v3xctrl_control.message import Command, Control, Latency, Telemetry


class TestNetworkCoordinator(unittest.TestCase):
    """Test suite for NetworkCoordinator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.model = ApplicationModel(
            fullscreen=False,
            throttle=0.0,
            steering=0.0
        )
        self.mock_osd = MagicMock()
        self.coordinator = NetworkCoordinator(self.model, self.mock_osd)

    def test_initialization(self):
        """Test NetworkCoordinator initialization."""
        self.assertEqual(self.coordinator.model, self.model)
        self.assertEqual(self.coordinator.osd, self.mock_osd)
        self.assertIsNone(self.coordinator.network_manager)
        self.assertIsInstance(self.coordinator.restart_complete, threading.Event)
        self.assertIsNone(self.coordinator.on_connection_change)

    @patch("v3xctrl_ui.NetworkManager.NetworkManager")
    def test_create_network_manager(self, mock_nm_class):
        """Test creating a network manager."""
        mock_settings = {"ports": {"video": 6666, "control": 6668}}
        mock_nm = MagicMock()
        mock_nm_class.return_value = mock_nm

        result = self.coordinator.create_network_manager(mock_settings)

        self.assertEqual(result, mock_nm)
        self.assertEqual(self.coordinator.network_manager, mock_nm)
        mock_nm_class.assert_called_once()

        # Verify handlers were created
        call_args = mock_nm_class.call_args
        self.assertEqual(call_args[0][0], mock_settings)
        handlers = call_args[0][1]
        self.assertIn("messages", handlers)
        self.assertIn("states", handlers)

    def test_setup_ports(self):
        """Test setting up network ports."""
        mock_nm = MagicMock()
        self.coordinator.network_manager = mock_nm

        self.coordinator.setup_ports()

        mock_nm.setup_ports.assert_called_once()

    def test_setup_ports_no_manager(self):
        """Test setting up ports when no network manager exists."""
        self.coordinator.network_manager = None
        # Should not raise an error
        self.coordinator.setup_ports()

    @patch("v3xctrl_ui.NetworkManager.NetworkManager")
    def test_restart_network_manager(self, mock_nm_class):
        """Test restarting network manager in background thread."""
        mock_settings = {"ports": {"video": 6666}}
        mock_nm_old = MagicMock()
        mock_nm_new = MagicMock()
        self.coordinator.network_manager = mock_nm_old

        # Set up the mock to return new network manager on second call
        mock_nm_class.return_value = mock_nm_new

        thread = self.coordinator.restart_network_manager(mock_settings)

        self.assertIsInstance(thread, threading.Thread)
        self.assertFalse(self.coordinator.restart_complete.is_set())

        # Run the thread
        thread.start()
        thread.join(timeout=1.0)

        # Verify restart completed
        self.assertTrue(self.coordinator.restart_complete.is_set())
        mock_nm_old.shutdown.assert_called_once()

    def test_send_control_message(self):
        """Test sending control message."""
        mock_server = MagicMock()
        mock_nm = MagicMock()
        mock_nm.server = mock_server
        mock_nm.server_error = False
        self.coordinator.network_manager = mock_nm

        self.coordinator.send_control_message(0.5, -0.3)

        mock_server.send.assert_called_once()
        call_args = mock_server.send.call_args[0][0]
        self.assertIsInstance(call_args, Control)

    def test_send_control_message_no_server(self):
        """Test sending control message when server is None."""
        mock_nm = MagicMock()
        mock_nm.server = None
        self.coordinator.network_manager = mock_nm

        # Should not raise an error
        self.coordinator.send_control_message(0.5, -0.3)

    def test_send_control_message_server_error(self):
        """Test sending control message when server has error."""
        mock_server = MagicMock()
        mock_nm = MagicMock()
        mock_nm.server = mock_server
        mock_nm.server_error = True
        self.coordinator.network_manager = mock_nm

        self.coordinator.send_control_message(0.5, -0.3)

        # Should not send when server has error
        mock_server.send.assert_not_called()

    def test_send_command(self):
        """Test sending a command to the server."""
        mock_server = MagicMock()
        mock_nm = MagicMock()
        mock_nm.server = mock_server
        self.coordinator.network_manager = mock_nm

        command = Command({"action": "test"})
        callback = MagicMock()

        self.coordinator.send_command(command, callback)

        mock_server.send_command.assert_called_once_with(command, callback)

    def test_send_command_no_server(self):
        """Test sending command when server is None."""
        mock_nm = MagicMock()
        mock_nm.server = None
        self.coordinator.network_manager = mock_nm

        command = Command({"action": "test"})
        callback = MagicMock()

        # Should log error but not raise
        self.coordinator.send_command(command, callback)

    def test_send_latency_check(self):
        """Test sending latency check."""
        mock_nm = MagicMock()
        self.coordinator.network_manager = mock_nm

        self.coordinator.send_latency_check()

        mock_nm.send_latency_check.assert_called_once()

    def test_update_ttl(self):
        """Test updating UDP TTL."""
        mock_nm = MagicMock()
        self.coordinator.network_manager = mock_nm

        self.coordinator.update_ttl(150)

        mock_nm.update_ttl.assert_called_once_with(150)

    def test_get_data_queue_size(self):
        """Test getting data queue size."""
        mock_nm = MagicMock()
        mock_nm.get_data_queue_size.return_value = 42
        self.coordinator.network_manager = mock_nm

        result = self.coordinator.get_data_queue_size()

        self.assertEqual(result, 42)

    def test_get_data_queue_size_no_manager(self):
        """Test getting data queue size when no network manager."""
        self.coordinator.network_manager = None

        result = self.coordinator.get_data_queue_size()

        self.assertEqual(result, 0)

    def test_get_video_buffer_size(self):
        """Test getting video buffer size."""
        mock_video_receiver = MagicMock()
        mock_video_receiver.frame_buffer = [1, 2, 3, 4, 5]
        mock_nm = MagicMock()
        mock_nm.video_receiver = mock_video_receiver
        self.coordinator.network_manager = mock_nm

        result = self.coordinator.get_video_buffer_size()

        self.assertEqual(result, 5)

    def test_get_video_buffer_size_no_receiver(self):
        """Test getting video buffer size when no video receiver."""
        mock_nm = MagicMock()
        mock_nm.video_receiver = None
        self.coordinator.network_manager = mock_nm

        result = self.coordinator.get_video_buffer_size()

        self.assertEqual(result, 0)

    def test_has_server_error(self):
        """Test checking for server error."""
        mock_nm = MagicMock()
        mock_nm.server_error = True
        self.coordinator.network_manager = mock_nm

        result = self.coordinator.has_server_error()

        self.assertTrue(result)

    def test_has_server_error_false(self):
        """Test checking for server error when no error."""
        mock_nm = MagicMock()
        mock_nm.server_error = False
        self.coordinator.network_manager = mock_nm

        result = self.coordinator.has_server_error()

        self.assertFalse(result)

    def test_is_control_connected(self):
        """Test checking control connection status."""
        self.model.control_connected = True

        result = self.coordinator.is_control_connected()

        self.assertTrue(result)

    def test_shutdown(self):
        """Test shutting down network manager."""
        mock_nm = MagicMock()
        self.coordinator.network_manager = mock_nm

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

        # Verify state handlers
        states = handlers["states"]
        self.assertEqual(len(states), 4)
        self.assertEqual(states[0][0], State.CONNECTED)
        self.assertEqual(states[1][0], State.DISCONNECTED)
        self.assertEqual(states[2][0], State.CONNECTED)
        self.assertEqual(states[3][0], State.DISCONNECTED)

    def test_handlers_update_connected_state(self):
        """Test that handlers update connection state correctly."""
        handlers = self.coordinator._create_handlers()

        # Get the connected and disconnected state handlers
        connected_handler = handlers["states"][2][1]
        disconnected_handler = handlers["states"][3][1]

        # Test connected
        self.assertFalse(self.model.control_connected)
        connected_handler()
        self.assertTrue(self.model.control_connected)

        # Test disconnected
        disconnected_handler()
        self.assertFalse(self.model.control_connected)

    def test_handlers_call_osd_methods(self):
        """Test that handlers call OSD methods."""
        handlers = self.coordinator._create_handlers()

        # Test message handlers
        telemetry_handler = handlers["messages"][0][1]
        latency_handler = handlers["messages"][1][1]

        mock_telemetry = MagicMock(spec=Telemetry)
        mock_latency = MagicMock(spec=Latency)

        telemetry_handler(mock_telemetry, "address")
        latency_handler(mock_latency, "address")

        self.assertEqual(self.mock_osd.message_handler.call_count, 2)

        # Test state handlers
        connect_handler = handlers["states"][0][1]
        disconnect_handler = handlers["states"][1][1]

        connect_handler()
        disconnect_handler()

        self.mock_osd.connect_handler.assert_called_once()
        self.mock_osd.disconnect_handler.assert_called_once()

    def test_connection_change_callback(self):
        """Test that connection change callback is invoked."""
        mock_callback = MagicMock()
        self.coordinator.on_connection_change = mock_callback

        handlers = self.coordinator._create_handlers()

        # Get connection state handlers
        connected_handler = handlers["states"][2][1]
        disconnected_handler = handlers["states"][3][1]

        # Test connected
        connected_handler()
        mock_callback.assert_called_with(True)

        # Test disconnected
        disconnected_handler()
        mock_callback.assert_called_with(False)

        self.assertEqual(mock_callback.call_count, 2)

    def test_connection_change_callback_not_set(self):
        """Test that missing callback doesn't cause errors."""
        self.coordinator.on_connection_change = None

        handlers = self.coordinator._create_handlers()
        connected_handler = handlers["states"][2][1]

        # Should not raise an error
        connected_handler()
        self.assertTrue(self.model.control_connected)


if __name__ == "__main__":
    unittest.main()
