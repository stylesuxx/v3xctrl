import unittest
from unittest.mock import MagicMock, patch

from src.v3xctrl_ui.AppState import AppState
from v3xctrl_helper.exceptions import UnauthorizedError


class TestAppState(unittest.TestCase):
    def setUp(self):
        # Patch Init.ui so no actual Pygame display is opened
        self.ui_patcher = patch("src.v3xctrl_ui.AppState.Init.ui", return_value=("screen", "clock"))
        self.mock_ui = self.ui_patcher.start()

        # Patch KeyAxisHandler so no real input logic runs
        self.keyaxis_patcher = patch("src.v3xctrl_ui.AppState.KeyAxisHandler")
        self.mock_keyaxis_cls = self.keyaxis_patcher.start()
        self.mock_keyaxis = MagicMock()
        self.mock_keyaxis.update.return_value = 0.5
        self.mock_keyaxis_cls.return_value = self.mock_keyaxis

        # Minimal settings mock
        self.settings = MagicMock()
        self.settings.get.return_value = {
            "keyboard": {
                "throttle_up": "w",
                "throttle_down": "s",
                "steering_right": "d",
                "steering_left": "a"
            }
        }

        self.app = AppState(
            (800, 600),
            "Test",
            video_port=5000,
            control_port=6000,
            server_handlers={},
            settings=self.settings
        )

    def tearDown(self):
        self.ui_patcher.stop()
        self.keyaxis_patcher.stop()

    def test_setup_relay_valid_and_invalid_port(self):
        # valid port string
        self.app.setup_relay("host:1234", "id1")
        self.assertEqual(self.app.relay_server, "host")
        self.assertEqual(self.app.relay_port, 1234)
        self.assertTrue(self.app.relay_enable)

        # invalid port string
        with patch("logging.warning") as log_warn:
            self.app.setup_relay("host:notaport", "id1")
            self.assertEqual(self.app.relay_port, 1234)  # unchanged
            log_warn.assert_called()

        # no colon path
        self.app.setup_relay("justhost", "id1")
        self.assertEqual(self.app.relay_server, "justhost")

    @patch("src.v3xctrl_ui.AppState.Init.video_receiver", return_value=MagicMock())
    @patch("src.v3xctrl_ui.AppState.Init.server", return_value=(MagicMock(), None))
    def test_setup_ports_success(self, mock_server, mock_vr):
        # Patch Peer.setup to return a fake address
        with patch("src.v3xctrl_ui.AppState.Peer.setup", return_value={"video": ("1.1.1.1", 1111)}) as mock_peer:
            self.app.setup_relay("relayhost:9000", "relayid")
            self.app.setup_ports()
            # Run the task synchronously
            self.app.video_receiver = None
            self.app.server = None
            mock_peer.assert_called()

    @patch("src.v3xctrl_ui.AppState.Init.video_receiver", return_value=MagicMock())
    @patch("src.v3xctrl_ui.AppState.Init.server", return_value=(MagicMock(), None))
    def test_setup_ports_unauthorized(self, mock_server, mock_vr):
        with patch("src.v3xctrl_ui.AppState.Peer.setup", side_effect=UnauthorizedError):
            self.app.setup_relay("relayhost:9000", "relayid")
            self.app.setup_ports()
            # Thread started, but UnauthorizedError sets message
            self.assertIn("unauthorized", self.app.relay_status_message.lower())

    def test_update_settings_sets_control_settings(self):
        new_settings = MagicMock()
        new_settings.get.return_value = {
            "keyboard": {
                "throttle_up": "w",
                "throttle_down": "s",
                "steering_right": "d",
                "steering_left": "a"
            }
        }
        self.app.update_settings(new_settings)
        self.assertEqual(self.app.settings, new_settings)

    def test_handle_control_with_and_without_gamepad(self):
        pressed_keys = MagicMock()
        gamepad_inputs = {"steering": 0.8, "throttle": 1.0, "brake": 0.2}

        # With server and no error
        mock_server = MagicMock()
        self.app.server = mock_server
        self.app.server_error = None

        self.app.handle_control(pressed_keys, None)
        self.assertEqual(self.app.throttle, 0.5)
        self.assertEqual(self.app.steering, 0.5)

        self.app.handle_control(pressed_keys, gamepad_inputs)
        self.assertAlmostEqual(self.app.steering, 0.8)
        self.assertAlmostEqual(self.app.throttle, 0.8)

        # Server.send should be called both times
        self.assertTrue(mock_server.send.called)

    def test_shutdown_stops_everything(self):
        mock_server = MagicMock()
        mock_vr = MagicMock()
        self.app.server = mock_server
        self.app.video_receiver = mock_vr

        with patch("pygame.quit") as quit_mock:
            self.app.shutdown()
            quit_mock.assert_called_once()
            mock_server.stop.assert_called_once()
            mock_server.join.assert_called_once()
            mock_vr.stop.assert_called_once()
            mock_vr.join.assert_called_once()
