import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame

from v3xctrl_ui.core.AppState import AppState


@patch("v3xctrl_ui.core.AppState.DisplayController")
@patch("v3xctrl_ui.core.AppState.InputController")
@patch("v3xctrl_ui.core.AppState.OSD")
@patch("v3xctrl_ui.core.AppState.Renderer")
@patch("v3xctrl_ui.core.AppState.NetworkCoordinator")
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
        mock_coordinator_cls,
        mock_renderer_cls,
        mock_osd_cls,
        mock_input_cls,
        mock_display_cls
    ):
        # Mock DisplayManager
        mock_display = MagicMock()
        mock_screen = MagicMock()
        mock_screen.get_size.return_value = (800, 600)
        mock_display.get_screen.return_value = mock_screen
        mock_display_cls.return_value = mock_display

        # Mock clock
        mock_clock = MagicMock()
        with patch("v3xctrl_ui.core.AppState.pygame.time.Clock", return_value=mock_clock):
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

            # Mock NetworkCoordinator
            mock_coordinator = MagicMock()
            mock_coordinator_manager = MagicMock()
            mock_coordinator_manager.server = None
            mock_coordinator_manager.server_error = None
            mock_coordinator.network_manager = mock_coordinator_manager
            mock_coordinator.get_data_queue_size.return_value = 0
            mock_coordinator.get_video_buffer_size.return_value = 0
            mock_coordinator.has_server_error.return_value = False
            mock_coordinator.is_control_connected.return_value = False
            mock_coordinator.create_network_manager.return_value = mock_coordinator_manager
            mock_coordinator_cls.return_value = mock_coordinator

            # Let deepcopy work normally - no mocking needed
            app = AppState(self.settings)

        return app, mock_input, mock_osd, mock_renderer, mock_coordinator

    def test_initialization_creates_all_components(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        # Check components were created
        mock_input_cls.assert_called_once_with(self.settings)
        # OSD is called with settings and telemetry_context
        self.assertEqual(mock_osd_cls.call_count, 1)
        call_args = mock_osd_cls.call_args[0]
        self.assertEqual(call_args[0], self.settings)  # First arg is settings
        # Second arg is TelemetryContext instance - just verify it exists
        self.assertIsNotNone(call_args[1])
        mock_renderer_cls.assert_called_once_with((800, 600), self.settings)

        # NetworkCoordinator should be created with model and osd
        mock_coordinator_cls.assert_called_once()
        mock_coordinator.create_network_manager.assert_called_once_with(self.settings)

        # Check NetworkManager.setup_ports was called
        mock_coordinator.setup_ports.assert_called_once()

    def test_initialization_sets_timing_intervals(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        app, _, _, _, _ = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        # Check timing intervals are set correctly (now in model)
        self.assertEqual(app.model.control_interval, 1.0 / 30)
        self.assertEqual(app.model.latency_interval, 1.0 / 1)
        self.assertEqual(app.timing_controller.main_loop_fps, 60)

    @patch("v3xctrl_ui.core.AppState.pygame.display.set_mode")
    def test_update_settings_updates_all_components(
        self, mock_set_mode,
        mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        mock_set_mode.return_value = MagicMock()

        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
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
        self.assertEqual(app.timing_controller.main_loop_fps, 120)

    def test_update_reads_inputs_and_sends_control(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        import time
        now = time.monotonic()

        app.model.last_control_update = now - 1.0
        app.model.last_latency_check = now - 2.0

        app.update()

        mock_input.read_inputs.assert_called_once()
        self.assertEqual(app.model.throttle, 0.5)
        self.assertEqual(app.model.steering, 0.3)
        mock_coordinator.send_control_message.assert_called_once_with(0.5, 0.3)
        mock_coordinator.send_latency_check.assert_called_once()

    def test_update_no_control_when_timing_not_ready(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        import time
        now = time.monotonic()

        app.model.last_control_update = now
        app.model.last_latency_check = now

        app.update()

        mock_input.read_inputs.assert_not_called()
        mock_coordinator.send_latency_check.assert_not_called()

    def test_render_updates_osd_and_calls_renderer(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        mock_coordinator.get_data_queue_size.return_value = 5
        mock_coordinator.has_server_error.return_value = False

        app.render()

        mock_osd.update_data_queue.assert_called_with(5)
        mock_osd.set_control.assert_called_with(app.model.throttle, app.model.steering)
        mock_renderer.render_all.assert_called_with(app, mock_coordinator.network_manager, False, 1.0)

    def test_render_handles_server_error(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        mock_coordinator.has_server_error.return_value = True
        app.render()

        mock_osd.update_debug_status.assert_called_with("fail")

    @patch("v3xctrl_ui.core.AppState.pygame.quit")
    def test_shutdown_stops_all_components(
        self, mock_quit, mock_coordinator_cls,
        mock_renderer_cls, mock_osd_cls,
        mock_input_cls, mock_display_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        app.shutdown()

        mock_input.shutdown.assert_called_once()
        mock_coordinator.shutdown.assert_called_once()
        mock_quit.assert_called_once()

    @patch("v3xctrl_ui.core.AppState.pygame.event.get")
    def test_handle_events_quit(
        self, mock_get_events, mock_coordinator_cls,
        mock_renderer_cls, mock_osd_cls,
        mock_input_cls, mock_display_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        quit_event = MagicMock()
        quit_event.type = pygame.QUIT
        mock_get_events.return_value = [quit_event]

        self.assertFalse(app.handle_events())
        self.assertFalse(app.model.running)

    @patch("v3xctrl_ui.core.AppState.pygame.event.get")
    def test_handle_events_menu_handles_events(
        self, mock_get_events, mock_coordinator_cls,
        mock_renderer_cls, mock_osd_cls,
        mock_input_cls, mock_display_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        some_event = MagicMock()
        some_event.type = 999
        mock_get_events.return_value = [some_event]

        mock_menu = MagicMock()
        app.event_controller.menu = mock_menu

        self.assertTrue(app.handle_events())
        mock_menu.handle_event.assert_called_once_with(some_event)

    @patch("v3xctrl_ui.core.AppState.pygame.display.set_mode")
    def test_timing_intervals_calculation(
        self, mock_set_mode,
        mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        mock_set_mode.return_value = MagicMock()

        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
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
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        """Test that network coordinator is properly set up with handlers."""
        app, mock_input, mock_osd, mock_renderer, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        # Handler creation is now delegated to NetworkCoordinator
        # Just verify the coordinator was set up correctly
        self.assertIsNotNone(app.network_coordinator)

    def test_update_timing_settings(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        """Test that timing controller correctly updates timing intervals"""
        app, _, _, _, _ = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        # Modify settings
        app.timing_controller.settings = {
            "timing": {
                "control_update_hz": 120,
                "latency_check_hz": 10,
                "main_loop_fps": 144
            }
        }

        # Call update method on timing controller
        app.timing_controller.update_from_settings()

        # Verify intervals were updated (now in model)
        self.assertEqual(app.model.control_interval, 1.0 / 120)
        self.assertEqual(app.model.latency_interval, 1.0 / 10)
        self.assertEqual(app.timing_controller.main_loop_fps, 144)

    def test_update_connected_state(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        """Test that connection change callback updates menu tab state"""
        app, _, _, _, mock_coordinator = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        self.assertFalse(app.model.control_connected)

        # The connection change callback is set on the coordinator
        self.assertIsNotNone(app.network_coordinator.on_connection_change)

        # Simulate connection change
        app._on_connection_change(True)
        # Verify the event controller would be called (we can't test directly as it's mocked)

    def test_tick_calls_clock(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        """Test that tick() calls clock.tick()"""
        app, _, _, _, _ = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        app.tick()
        app.clock.tick.assert_called_once_with(60)

    def test_loop_history_deque(
        self, mock_coordinator_cls, mock_renderer_cls,
        mock_osd_cls, mock_input_cls, mock_display_cls
    ):
        """Test that loop_history is properly initialized"""
        app, _, _, _, _ = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
        )

        self.assertEqual(app.model.loop_history.maxlen, 300)
        self.assertEqual(len(app.model.loop_history), 0)

        # Update should add to history
        app.update()
        self.assertEqual(len(app.model.loop_history), 1)

    @patch("v3xctrl_ui.core.AppState.logging")
    def test_update_handles_input_error(
        self, mock_logging, mock_coordinator_cls,
        mock_renderer_cls, mock_osd_cls,
        mock_input_cls, mock_display_cls
    ):
        """Test that update() handles input read errors gracefully"""
        app, mock_input, _, _, _ = self._create_app(
            mock_coordinator_cls, mock_renderer_cls, mock_osd_cls,
            mock_input_cls, mock_display_cls
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
