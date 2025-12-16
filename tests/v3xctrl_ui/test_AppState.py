import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch, call

import pygame

from src.v3xctrl_ui.AppState import AppState


@patch("src.v3xctrl_ui.AppState.Init")
@patch("src.v3xctrl_ui.AppState.InputManager")
@patch("src.v3xctrl_ui.AppState.OSD")
@patch("src.v3xctrl_ui.AppState.Renderer")
@patch("src.v3xctrl_ui.AppState.NetworkManager")
class TestAppState(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "timing": {
                "control_update_hz": 30,
                "latency_check_hz": 1,
                "main_loop_fps": 60
            },
            "video": {
                "width": 800,
                "height": 600,
                "fullscreen": False
            },
            "settings": {
                "title": "Test"
            },
            "ports": {
                "video": 6666,
                "control": 6668
            },
            "relay": {}  # Add relay to initial settings
        }

    def _create_app(
        self,
        mock_network_cls,
        mock_renderer_cls,
        mock_osd_cls,
        mock_input_cls,
        mock_init_cls
    ):
        # Mock Init.ui to return screen and clock
        mock_screen = MagicMock()
        mock_screen.get_size.return_value = (800, 600)
        mock_clock = MagicMock()
        mock_init_cls.ui.return_value = (mock_screen, mock_clock)

        # Mock InputManager
        mock_input = MagicMock()
        mock_input.read_inputs.return_value = (0.5, 0.3)
        mock_input.gamepad_manager = MagicMock()
        mock_input_cls.return_value = mock_input

        # Mock OSD
        mock_osd = MagicMock()
        mock_osd_cls.return_value = mock_osd

        # Mock Renderer
        mock_renderer = MagicMock()
        mock_renderer_cls.return_value = mock_renderer

        # Mock NetworkManager
        mock_network = MagicMock()
        mock_network.server = None
        mock_network.server_error = None
        mock_network.get_data_queue_size.return_value = 0
        mock_network_cls.return_value = mock_network

        # Let deepcopy work normally - no mocking needed
        app = AppState(self.settings)

        return app, mock_input, mock_osd, mock_renderer, mock_network

    def test_initialization_creates_all_components(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        # Check components were created
        mock_input_cls.assert_called_once_with(self.settings)
        mock_osd_cls.assert_called_once_with(self.settings)
        mock_renderer_cls.assert_called_once_with((800, 600), self.settings)

        # NetworkManager should be created with settings and handlers
        mock_network_cls.assert_called_once()
        call_args = mock_network_cls.call_args
        # First arg should be settings dict
        self.assertIsInstance(call_args[0][0], dict)
        self.assertIn("timing", call_args[0][0])
        # Second arg should be handlers dict
        self.assertIsInstance(call_args[0][1], dict)
        self.assertIn("messages", call_args[0][1])
        self.assertIn("states", call_args[0][1])

        # Check NetworkManager.setup_ports was called
        mock_network.setup_ports.assert_called_once()

    def test_initialization_sets_timing_intervals(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, _, _, _, _ = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        # Check timing intervals are set correctly (now in model)
        self.assertEqual(app.model.control_interval, 1.0 / 30)
        self.assertEqual(app.model.latency_interval, 1.0 / 1)
        self.assertEqual(app.main_loop_fps, 60)

    @patch("src.v3xctrl_ui.AppState.pygame.display.set_mode")
    def test_update_settings_updates_all_components(
        self, mock_set_mode,
        mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        mock_set_mode.return_value = MagicMock()

        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        new_settings = {
            "timing": {
                "control_update_hz": 60,
                "latency_check_hz": 2,
                "main_loop_fps": 120
            },
            "video": {
                "fullscreen": False
            },
            "ports": self.settings["ports"],  # Include ports to avoid restart
            "relay": {}  # Include relay to avoid restart
        }

        app.update_settings(new_settings)

        self.assertEqual(app.settings, new_settings)
        mock_input.update_settings.assert_called_with(new_settings)
        mock_osd.update_settings.assert_called_with(new_settings)
        self.assertEqual(mock_renderer.settings, new_settings)

        # Check timing intervals were updated (now in model)
        self.assertEqual(app.model.control_interval, 1.0 / 60)
        self.assertEqual(app.model.latency_interval, 1.0 / 2)
        self.assertEqual(app.main_loop_fps, 120)

    def test_update_reads_inputs_and_sends_control(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        import time
        now = time.monotonic()

        app.model.last_control_update = now - 1.0
        app.model.last_latency_check = now - 2.0

        mock_network.server = MagicMock()
        mock_network.server_error = None

        app.update()

        mock_input.read_inputs.assert_called_once()
        self.assertEqual(app.model.throttle, 0.5)
        self.assertEqual(app.model.steering, 0.3)
        mock_network.server.send.assert_called_once()
        mock_network.send_latency_check.assert_called_once()

    def test_update_no_control_when_timing_not_ready(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        import time
        now = time.monotonic()

        app.model.last_control_update = now
        app.model.last_latency_check = now

        app.update()

        mock_input.read_inputs.assert_not_called()
        mock_network.send_latency_check.assert_not_called()

    def test_send_control_message_with_server(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        mock_network.server = MagicMock()
        mock_network.server_error = None

        app.model.throttle = 0.7
        app.model.steering = -0.4

        app._send_control_message()

        mock_network.server.send.assert_called_once()
        self.assertEqual(
            mock_network.server.send.call_args[0][0].__class__.__name__,
            'Control'
        )

    def test_send_control_message_no_server(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        mock_network.server = None
        app._send_control_message()

        # Should not crash, just return early

    def test_send_control_message_with_server_error(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        mock_network.server = MagicMock()
        mock_network.server_error = "Connection failed"

        app._send_control_message()

        mock_network.server.send.assert_not_called()

    def test_render_updates_osd_and_calls_renderer(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        mock_network.get_data_queue_size.return_value = 5
        mock_network.server_error = None

        app.render()

        mock_osd.update_data_queue.assert_called_with(5)
        mock_osd.set_control.assert_called_with(app.model.throttle, app.model.steering)
        mock_renderer.render_all.assert_called_with(app, mock_network, False, 1)

    def test_render_handles_server_error(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        mock_network.server_error = "Connection failed"
        app.render()

        mock_osd.update_debug_status.assert_called_with("fail")

    @patch("src.v3xctrl_ui.AppState.pygame.quit")
    def test_shutdown_stops_all_components(
        self, mock_quit, mock_network_cls,
        mock_renderer_cls, mock_osd_cls,
        mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        app.shutdown()

        mock_input.shutdown.assert_called_once()
        mock_network.shutdown.assert_called_once()
        mock_quit.assert_called_once()

    @patch("src.v3xctrl_ui.AppState.pygame.event.get")
    def test_handle_events_quit(
        self, mock_get_events, mock_network_cls,
        mock_renderer_cls, mock_osd_cls,
        mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        quit_event = MagicMock()
        quit_event.type = pygame.QUIT
        mock_get_events.return_value = [quit_event]

        self.assertFalse(app.handle_events())
        self.assertFalse(app.model.running)

    @patch("src.v3xctrl_ui.AppState.pygame.event.get")
    def test_handle_events_menu_handles_events(
        self, mock_get_events, mock_network_cls,
        mock_renderer_cls, mock_osd_cls,
        mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        some_event = MagicMock()
        some_event.type = 999
        mock_get_events.return_value = [some_event]

        mock_menu = MagicMock()
        app.event_controller.menu = mock_menu

        self.assertTrue(app.handle_events())
        mock_menu.handle_event.assert_called_once_with(some_event)

    @patch("src.v3xctrl_ui.AppState.pygame.display.set_mode")
    def test_timing_intervals_calculation(
        self, mock_set_mode,
        mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        mock_set_mode.return_value = MagicMock()

        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        self.assertEqual(app.model.control_interval, 1.0 / 30)
        self.assertEqual(app.model.latency_interval, 1.0 / 1)

        new_settings = {
            "timing": {
                "control_update_hz": 60,
                "latency_check_hz": 5,
                "main_loop_fps": 60
            },
            "video": {
                "fullscreen": False
            },
            "ports": self.settings["ports"],  # Include ports to avoid restart
            "relay": {}  # Include relay to avoid restart
        }

        app.update_settings(new_settings)

        self.assertEqual(app.model.control_interval, 1.0 / 60)
        self.assertEqual(app.model.latency_interval, 1.0 / 5)

    def test_handlers_creation(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        handlers = app._create_handlers()

        self.assertIn("messages", handlers)
        self.assertIn("states", handlers)
        self.assertEqual(len(handlers["messages"]), 2)
        self.assertEqual(len(handlers["states"]), 4)

    def test_update_timing_settings(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        """Test that _update_timing_settings correctly updates timing intervals"""
        app, _, _, _, _ = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        # Modify settings
        app.settings["timing"] = {
            "control_update_hz": 120,
            "latency_check_hz": 10,
            "main_loop_fps": 144
        }

        # Call update method
        app._update_timing_settings()

        # Verify intervals were updated (now in model)
        self.assertEqual(app.model.control_interval, 1.0 / 120)
        self.assertEqual(app.model.latency_interval, 1.0 / 10)
        self.assertEqual(app.main_loop_fps, 144)

    def test_update_connected_state(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        """Test that _update_connected updates control_connected state"""
        app, _, _, _, _ = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        self.assertFalse(app.model.control_connected)

        app._update_connected(True)
        self.assertTrue(app.model.control_connected)

        app._update_connected(False)
        self.assertFalse(app.model.control_connected)

    def test_settings_equal_method(
        self, mock_network_cls,
        mock_renderer_cls, mock_osd_cls,
        mock_input_cls, mock_init_cls
    ):
        """Test that _settings_equal correctly compares settings"""
        app, _, _, _, _ = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        # Same settings should return True
        same_settings = {
            "ports": {
                "video": 6666,
                "control": 6668
            }
        }
        self.assertTrue(app._settings_equal(same_settings, "ports"))

        # Different settings should return False
        different_settings = {
            "ports": {
                "video": 7777,
                "control": 6668
            }
        }
        self.assertFalse(app._settings_equal(different_settings, "ports"))

    def test_tick_calls_clock(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        """Test that tick() calls clock.tick()"""
        app, _, _, _, _ = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        app.tick()
        app.clock.tick.assert_called_once_with(60)

    def test_loop_history_deque(
        self, mock_network_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_init_cls
    ):
        """Test that loop_history is properly initialized"""
        app, _, _, _, _ = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        self.assertEqual(app.model.loop_history.maxlen, 300)
        self.assertEqual(len(app.model.loop_history), 0)

        # Update should add to history
        app.update()
        self.assertEqual(len(app.model.loop_history), 1)

    @patch("src.v3xctrl_ui.AppState.logging")
    def test_update_handles_input_error(
        self, mock_logging, mock_network_cls,
        mock_renderer_cls, mock_osd_cls,
        mock_input_cls, mock_init_cls
    ):
        """Test that update() handles input read errors gracefully"""
        app, mock_input, _, _, _ = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_init_cls
        )

        # Make read_inputs raise an exception
        mock_input.read_inputs.side_effect = Exception("Input error")

        import time
        app.model.last_control_update = time.monotonic() - 1.0

        # Should not crash
        app.update()

        # Should log warning
        mock_logging.warning.assert_called()


if __name__ == '__main__':
    unittest.main()
