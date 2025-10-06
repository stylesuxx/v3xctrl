import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame

from src.v3xctrl_ui.AppState import AppState


@patch("src.v3xctrl_ui.AppState.InputManager")
@patch("src.v3xctrl_ui.AppState.OSD")
@patch("src.v3xctrl_ui.AppState.Renderer")
@patch("src.v3xctrl_ui.AppState.NetworkManager")
class TestAppState(unittest.TestCase):
    def setUp(self):
        self.settings = MagicMock()
        self.settings.get.side_effect = lambda key, default=None: {
            "timing": {"control_update_hz": 30, "latency_check_hz": 1}
        }.get(key, default)

    def _create_app(
        self,
        mock_network_cls,
        mock_renderer_cls,
        mock_osd_cls,
        mock_input_cls
    ):
        mock_input = MagicMock()
        mock_input.read_inputs.return_value = (0.5, 0.3)
        mock_input.gamepad_manager = MagicMock()
        mock_input_cls.return_value = mock_input

        mock_osd = MagicMock()
        mock_osd_cls.return_value = mock_osd

        mock_renderer = MagicMock()
        mock_renderer_cls.return_value = mock_renderer

        mock_network = MagicMock()
        mock_network.server = None
        mock_network.server_error = None
        mock_network.get_data_queue_size.return_value = 0
        mock_network_cls.return_value = mock_network

        app = AppState(
            (800, 600),
            "Test",
            video_port=5000,
            control_port=6000,
            settings=self.settings
        )

        return app, mock_input, mock_osd, mock_renderer, mock_network

    def test_initialization_creates_all_components(self, mock_network_cls,
                                                  mock_renderer_cls, mock_osd_cls,
                                                  mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        mock_input_cls.assert_called_once_with(self.settings)
        mock_osd_cls.assert_called_once_with(self.settings)
        mock_renderer_cls.assert_called_once_with((800, 600), self.settings)
        mock_network_cls.assert_called_once()

        args, kwargs = mock_network_cls.call_args
        self.assertEqual(args[0], 5000)
        self.assertEqual(args[1], 6000)
        self.assertEqual(args[2], self.settings)
        self.assertIsNotNone(args[3])

    @patch("src.v3xctrl_ui.AppState.pygame.display.set_mode", return_value=pygame.Surface((800,600)))
    def test_update_settings_updates_all_components(
        self, mock_set_mode, mock_network_cls,
        mock_renderer_cls, mock_osd_cls, mock_input_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls
        )

        new_settings = MagicMock()
        new_settings.get.side_effect = lambda key, default=None: {
            "timing": {"control_update_hz": 60, "latency_check_hz": 2}
        }.get(key, default)

        app.update_settings(new_settings)

        self.assertEqual(app.settings, new_settings)
        mock_input.update_settings.assert_called_with(new_settings)
        mock_osd.update_settings.assert_called_with(new_settings)
        self.assertEqual(mock_renderer.settings, new_settings)

    def test_update_reads_inputs_and_sends_control(self, mock_network_cls,
                                                  mock_renderer_cls, mock_osd_cls,
                                                  mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        import time
        now = time.monotonic()

        app.last_control_update = now - 1.0
        app.last_latency_check = now - 2.0

        mock_network.server = MagicMock()
        mock_network.server_error = None

        app.update(now)

        mock_input.read_inputs.assert_called_once()
        self.assertEqual(app.throttle, 0.5)
        self.assertEqual(app.steering, 0.3)
        mock_network.server.send.assert_called_once()
        mock_network.send_latency_check.assert_called_once()

    def test_update_no_control_when_timing_not_ready(self, mock_network_cls,
                                                    mock_renderer_cls, mock_osd_cls,
                                                    mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        import time
        now = time.monotonic()

        app.last_control_update = now
        app.last_latency_check = now

        app.update(now)

        mock_input.read_inputs.assert_not_called()
        mock_network.send_latency_check.assert_not_called()

    def test_send_control_message_with_server(self, mock_network_cls,
                                             mock_renderer_cls, mock_osd_cls,
                                             mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        mock_network.server = MagicMock()
        mock_network.server_error = None

        app.throttle = 0.7
        app.steering = -0.4

        app._send_control_message()

        mock_network.server.send.assert_called_once()
        self.assertEqual(mock_network.server.send.call_args[0][0].__class__.__name__, 'Control')

    def test_send_control_message_no_server(self, mock_network_cls,
                                           mock_renderer_cls, mock_osd_cls,
                                           mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        mock_network.server = None
        app._send_control_message()

    def test_send_control_message_with_server_error(self, mock_network_cls,
                                                   mock_renderer_cls, mock_osd_cls,
                                                   mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        mock_network.server = MagicMock()
        mock_network.server_error = "Connection failed"

        app._send_control_message()

        mock_network.server.send.assert_not_called()

    def test_render_updates_osd_and_calls_renderer(self, mock_network_cls,
                                                  mock_renderer_cls, mock_osd_cls,
                                                  mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        mock_network.get_data_queue_size.return_value = 5
        mock_network.server_error = None

        app.render()

        mock_osd.update_data_queue.assert_called_with(5)
        mock_osd.set_control.assert_called_with(app.throttle, app.steering)
        mock_renderer.render_all.assert_called_with(app, mock_network, False, 1)

    def test_render_handles_server_error(self, mock_network_cls,
                                        mock_renderer_cls, mock_osd_cls,
                                        mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        mock_network.server_error = "Connection failed"
        app.render()

        mock_osd.update_debug_status.assert_called_with("fail")

    @patch("src.v3xctrl_ui.AppState.pygame.quit")
    def test_shutdown_stops_all_components(self, mock_quit, mock_network_cls,
                                          mock_renderer_cls, mock_osd_cls,
                                          mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        app.shutdown()

        mock_input.shutdown.assert_called_once()
        mock_network.shutdown.assert_called_once()
        mock_quit.assert_called_once()

    @patch("src.v3xctrl_ui.AppState.pygame.event.get")
    def test_handle_events_quit(self, mock_get_events, mock_network_cls,
                               mock_renderer_cls, mock_osd_cls, mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        import pygame

        quit_event = MagicMock()
        quit_event.type = pygame.QUIT
        mock_get_events.return_value = [quit_event]

        self.assertFalse(app.handle_events())
        self.assertFalse(app.running)

    @patch("src.v3xctrl_ui.AppState.pygame.event.get")
    def test_handle_events_menu_handles_events(self, mock_get_events,
                                              mock_network_cls, mock_renderer_cls,
                                              mock_osd_cls, mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        some_event = MagicMock()
        some_event.type = 999
        mock_get_events.return_value = [some_event]

        mock_menu = MagicMock()
        app.menu = mock_menu

        self.assertTrue(app.handle_events())
        mock_menu.handle_event.assert_called_once_with(some_event)

    def test_initialize_timing(self, mock_network_cls, mock_renderer_cls,
                              mock_osd_cls, mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        start_time = 123.456
        app.initialize_timing(start_time)

        self.assertEqual(app.last_control_update, start_time)
        self.assertEqual(app.last_latency_check, start_time)

    @patch("src.v3xctrl_ui.AppState.pygame.display.set_mode", return_value=pygame.Surface((800,600)))
    def test_timing_intervals_calculation(
        self, mock_set_mode, mock_network_cls,
        mock_renderer_cls, mock_osd_cls, mock_input_cls
    ):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        self.assertEqual(app.control_interval, 1.0 / 30)
        self.assertEqual(app.latency_interval, 1.0 / 1)

        new_settings = MagicMock()
        new_settings.get.side_effect = lambda key, default=None: {
            "timing": {"control_update_hz": 60, "latency_check_hz": 5}
        }.get(key, default)

        app.update_settings(new_settings)

        self.assertEqual(app.control_interval, 1.0 / 60)
        self.assertEqual(app.latency_interval, 1.0 / 5)

    def test_osd_handlers_creation(self, mock_network_cls, mock_renderer_cls,
                                  mock_osd_cls, mock_input_cls):
        app, mock_input, mock_osd, mock_renderer, mock_network = self._create_app(
            mock_network_cls, mock_renderer_cls, mock_osd_cls, mock_input_cls)

        handlers = app._create_handlers()

        self.assertIn("messages", handlers)
        self.assertIn("states", handlers)
        self.assertEqual(len(handlers["messages"]), 2)
        self.assertEqual(len(handlers["states"]), 4)


if __name__ == '__main__':
    unittest.main()
