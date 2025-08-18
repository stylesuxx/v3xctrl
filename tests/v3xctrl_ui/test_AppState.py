import unittest
from unittest.mock import MagicMock, patch

from src.v3xctrl_ui.AppState import AppState


class TestAppState(unittest.TestCase):
    def setUp(self):
        # Patch Init.ui so no actual Pygame display is opened
        self.ui_patcher = patch("src.v3xctrl_ui.AppState.Init.ui", return_value=("screen", "clock"))
        self.mock_ui = self.ui_patcher.start()

        # Patch InputManager
        self.input_patcher = patch("src.v3xctrl_ui.AppState.InputManager")
        self.mock_input_cls = self.input_patcher.start()
        self.mock_input = MagicMock()
        self.mock_input.read_inputs.return_value = (0.5, 0.3)  # (throttle, steering)
        self.mock_input.gamepad_manager = MagicMock()
        self.mock_input_cls.return_value = self.mock_input

        # Patch OSD
        self.osd_patcher = patch("src.v3xctrl_ui.AppState.OSD")
        self.mock_osd_cls = self.osd_patcher.start()
        self.mock_osd = MagicMock()
        self.mock_osd_cls.return_value = self.mock_osd

        # Patch Renderer
        self.renderer_patcher = patch("src.v3xctrl_ui.AppState.Renderer")
        self.mock_renderer_cls = self.renderer_patcher.start()
        self.mock_renderer = MagicMock()
        self.mock_renderer_cls.return_value = self.mock_renderer

        # Patch NetworkManager
        self.network_patcher = patch("src.v3xctrl_ui.AppState.NetworkManager")
        self.mock_network_cls = self.network_patcher.start()
        self.mock_network = MagicMock()
        self.mock_network.server = None
        self.mock_network.server_error = None
        self.mock_network.get_data_queue_size.return_value = 0
        self.mock_network_cls.return_value = self.mock_network

        # Patch signal handling
        self.signal_patcher = patch("src.v3xctrl_ui.AppState.signal")
        self.mock_signal = self.signal_patcher.start()

        # Minimal settings mock
        self.settings = MagicMock()
        self.settings.get.side_effect = lambda key, default=None: {
            "timing": {"control_update_hz": 30, "latency_check_hz": 1}
        }.get(key, default)

        self.app = AppState(
            (800, 600),
            "Test",
            video_port=5000,
            control_port=6000,
            settings=self.settings
        )

    def tearDown(self):
        self.ui_patcher.stop()
        self.input_patcher.stop()
        self.osd_patcher.stop()
        self.renderer_patcher.stop()
        self.network_patcher.stop()
        self.signal_patcher.stop()

    def test_initialization_creates_all_components(self):
        """Test that AppState properly initializes all components."""
        self.mock_input_cls.assert_called_once_with(self.settings)
        self.mock_osd_cls.assert_called_once_with(self.settings)
        self.mock_renderer_cls.assert_called_once_with((800, 600), self.settings)
        self.mock_network_cls.assert_called_once()

        # Verify NetworkManager was called with correct parameters
        args, kwargs = self.mock_network_cls.call_args
        self.assertEqual(args[0], 5000)  # video_port
        self.assertEqual(args[1], 6000)  # control_port
        self.assertEqual(args[2], self.settings)  # settings
        self.assertIsNotNone(args[3])  # osd_handlers

    def test_update_settings_updates_all_components(self):
        """Test that update_settings properly updates all components."""
        new_settings = MagicMock()
        new_settings.get.side_effect = lambda key, default=None: {
            "timing": {"control_update_hz": 60, "latency_check_hz": 2}
        }.get(key, default)

        self.app.update_settings(new_settings)

        self.assertEqual(self.app.settings, new_settings)
        self.mock_input.update_settings.assert_called_with(new_settings)
        self.mock_osd.update_settings.assert_called_with(new_settings)
        self.assertEqual(self.mock_renderer.settings, new_settings)

    def test_update_reads_inputs_and_sends_control(self):
        """Test that update method reads inputs and sends control messages."""
        import time
        now = time.monotonic()

        # Set up timing so control update should trigger
        self.app.last_control_update = now - 1.0  # Force control update
        self.app.last_latency_check = now - 2.0   # Force latency check

        # Mock server available
        self.mock_network.server = MagicMock()
        self.mock_network.server_error = None

        self.app.update(now)

        # Verify inputs were read
        self.mock_input.read_inputs.assert_called_once()

        # Verify control values were set from input manager
        self.assertEqual(self.app.throttle, 0.5)
        self.assertEqual(self.app.steering, 0.3)

        # Verify control message was sent
        self.mock_network.server.send.assert_called_once()

        # Verify latency check was sent
        self.mock_network.send_latency_check.assert_called_once()

    def test_update_no_control_when_timing_not_ready(self):
        """Test that update doesn't read inputs when timing hasn't elapsed."""
        import time
        now = time.monotonic()

        # Set timing so no updates should trigger
        self.app.last_control_update = now  # Recent update
        self.app.last_latency_check = now   # Recent check

        self.app.update(now)

        # Verify inputs were not read
        self.mock_input.read_inputs.assert_not_called()

        # Verify no latency check was sent
        self.mock_network.send_latency_check.assert_not_called()

    def test_send_control_message_with_server(self):
        """Test that _send_control_message works with available server."""
        # Mock server available
        self.mock_network.server = MagicMock()
        self.mock_network.server_error = None

        # Set some control values
        self.app.throttle = 0.7
        self.app.steering = -0.4

        self.app._send_control_message()

        # Verify control message was sent with correct values
        self.mock_network.server.send.assert_called_once()
        call_args = self.mock_network.server.send.call_args[0][0]

        # Check that it's a Control message with correct data
        self.assertEqual(call_args.__class__.__name__, 'Control')

    def test_send_control_message_no_server(self):
        """Test that _send_control_message handles missing server gracefully."""
        # No server available
        self.mock_network.server = None

        self.app._send_control_message()

        # Should not raise exception, just do nothing

    def test_send_control_message_with_server_error(self):
        """Test that _send_control_message handles server errors."""
        # Server with error
        self.mock_network.server = MagicMock()
        self.mock_network.server_error = "Connection failed"

        self.app._send_control_message()

        # Should not send when there's an error
        self.mock_network.server.send.assert_not_called()

    def test_render_updates_osd_and_calls_renderer(self):
        """Test that render method properly updates OSD and calls renderer."""
        self.mock_network.get_data_queue_size.return_value = 5
        self.mock_network.server_error = None

        self.app.render()

        # Verify OSD was updated
        self.mock_osd.update_data_queue.assert_called_with(5)
        self.mock_osd.set_control.assert_called_with(self.app.throttle, self.app.steering)

        # Verify renderer was called
        self.mock_renderer.render_all.assert_called_with(self.app, self.mock_network)

    def test_render_handles_server_error(self):
        """Test that render method handles server errors."""
        self.mock_network.server_error = "Connection failed"

        self.app.render()

        # Verify OSD was notified of failure
        self.mock_osd.update_debug_status.assert_called_with("fail")

    def test_shutdown_stops_all_components(self):
        """Test that shutdown properly stops all components."""
        with patch("src.v3xctrl_ui.AppState.pygame.quit") as mock_quit:
            self.app.shutdown()

            # Verify all components were shut down
            self.mock_input.shutdown.assert_called_once()
            self.mock_network.shutdown.assert_called_once()
            mock_quit.assert_called_once()

    @patch("src.v3xctrl_ui.AppState.pygame.event.get")
    def test_handle_events_quit(self, mock_get_events):
        """Test that handle_events properly handles quit event."""
        import pygame

        quit_event = MagicMock()
        quit_event.type = pygame.QUIT
        mock_get_events.return_value = [quit_event]

        result = self.app.handle_events()

        self.assertFalse(result)
        self.assertFalse(self.app.running)

    @patch("src.v3xctrl_ui.AppState.pygame.event.get")
    def test_handle_events_escape_toggles_menu(self, mock_get_events):
        """Test that handle_events properly toggles menu on escape."""
        import pygame

        escape_event = MagicMock()
        escape_event.type = pygame.KEYDOWN
        escape_event.key = pygame.K_ESCAPE
        mock_get_events.return_value = [escape_event]

        with patch("src.v3xctrl_ui.AppState.Menu") as mock_menu_cls:
            mock_menu = MagicMock()
            mock_menu_cls.return_value = mock_menu

            # Verify initial state - no menu
            self.assertIsNone(self.app.menu)

            # First call should create menu
            result = self.app.handle_events()
            self.assertTrue(result)
            self.assertTrue(self.app.running)

            # Verify menu was created with correct parameters
            mock_menu_cls.assert_called_once_with(
                800, 600,  # size
                self.mock_input.gamepad_manager,  # gamepad manager from input manager
                self.settings,
                self.app.update_settings,
                self.mock_network.server
            )
            self.assertEqual(self.app.menu, mock_menu)

            # Reset for second test
            mock_get_events.return_value = [escape_event]

            # Second call should remove menu
            result = self.app.handle_events()
            self.assertTrue(result)
            self.assertTrue(self.app.running)
            self.assertIsNone(self.app.menu)

    @patch("src.v3xctrl_ui.AppState.pygame.event.get")
    def test_handle_events_menu_handles_events(self, mock_get_events):
        """Test that events are passed to menu when menu is active."""
        some_event = MagicMock()
        some_event.type = 999  # Some other event type
        mock_get_events.return_value = [some_event]

        # Create a mock menu
        mock_menu = MagicMock()
        self.app.menu = mock_menu

        result = self.app.handle_events()

        # Verify event was passed to menu
        mock_menu.handle_event.assert_called_once_with(some_event)
        self.assertTrue(result)

    def test_initialize_timing(self):
        """Test that timing initialization works correctly."""
        start_time = 123.456

        self.app.initialize_timing(start_time)

        self.assertEqual(self.app.last_control_update, start_time)
        self.assertEqual(self.app.last_latency_check, start_time)

    def test_timing_intervals_calculation(self):
        """Test that timing intervals are calculated correctly from settings."""
        # Verify initial timing calculation
        self.assertEqual(self.app.control_interval, 1.0 / 30)  # 30 Hz
        self.assertEqual(self.app.latency_interval, 1.0 / 1)   # 1 Hz

        # Test with different timing settings
        new_settings = MagicMock()
        new_settings.get.side_effect = lambda key, default=None: {
            "timing": {"control_update_hz": 60, "latency_check_hz": 5}
        }.get(key, default)

        self.app.update_settings(new_settings)

        self.assertEqual(self.app.control_interval, 1.0 / 60)  # 60 Hz
        self.assertEqual(self.app.latency_interval, 1.0 / 5)   # 5 Hz

    def test_osd_handlers_creation(self):
        """Test that OSD handlers are created correctly."""
        handlers = self.app._create_osd_handlers()

        # Verify structure
        self.assertIn("messages", handlers)
        self.assertIn("states", handlers)

        # Verify message handlers
        message_handlers = handlers["messages"]
        self.assertEqual(len(message_handlers), 2)

        # Verify state handlers
        state_handlers = handlers["states"]
        self.assertEqual(len(state_handlers), 2)


if __name__ == '__main__':
    unittest.main()
