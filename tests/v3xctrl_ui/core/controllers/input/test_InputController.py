import unittest
from unittest.mock import MagicMock, patch, call

from v3xctrl_ui.core.controllers.input.InputController import InputController


@patch("v3xctrl_ui.core.controllers.input.InputController.GamepadController")
@patch("v3xctrl_ui.core.controllers.input.InputController.KeyAxisHandler")
@patch("v3xctrl_ui.core.controllers.input.InputController.pygame")
class TestInputController(unittest.TestCase):
    def setUp(self):
        self.settings = MagicMock()
        self.settings.get.side_effect = lambda key, default=None: {
            "calibrations": {"gamepad1": {"deadzone": 0.1}},
            "input": {"guid": "gamepad1"},
            "controls": {
                "keyboard": {
                    "throttle_up": "w",
                    "throttle_down": "s",
                    "steering_right": "d",
                    "steering_left": "a"
                }
            }
        }.get(key, default)

    def _setup_mocks(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad = MagicMock()
        mock_gamepad_cls.return_value = mock_gamepad

        mock_throttle_handler = MagicMock()
        mock_steering_handler = MagicMock()

        return mock_gamepad, mock_throttle_handler, mock_steering_handler

    def test_initialization_creates_components(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, mock_throttle_handler, mock_steering_handler = self._setup_mocks(
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        mock_keyaxis_cls.side_effect = [mock_throttle_handler, mock_steering_handler]

        input_manager = InputController(self.settings)

        mock_gamepad_cls.assert_called_once()
        mock_gamepad.set_calibration.assert_called_with("gamepad1", {"deadzone": 0.1})
        mock_gamepad.set_active.assert_called_with("gamepad1")
        mock_gamepad.start.assert_called_once()

        self.assertEqual(mock_keyaxis_cls.call_count, 2)

        throttle_call = mock_keyaxis_cls.call_args_list[0]
        self.assertEqual(throttle_call[1]["positive"], "w")
        self.assertEqual(throttle_call[1]["negative"], "s")
        self.assertEqual(throttle_call[1]["min_val"], -1.0)
        self.assertEqual(throttle_call[1]["max_val"], 1.0)

        steering_call = mock_keyaxis_cls.call_args_list[1]
        self.assertEqual(steering_call[1]["positive"], "d")
        self.assertEqual(steering_call[1]["negative"], "a")
        self.assertEqual(steering_call[1]["min_val"], -1.0)
        self.assertEqual(steering_call[1]["max_val"], 1.0)

    def test_initialization_no_keyboard_controls(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)

        no_controls_settings = MagicMock()
        no_controls_settings.get.side_effect = lambda key, default=None: {
            "calibrations": {},
            "input": {},
            "controls": {}
        }.get(key, default)

        input_manager = InputController(no_controls_settings)

        mock_gamepad_cls.assert_called_once()
        self.assertEqual(len(input_manager.key_handlers), 0)

    def test_read_inputs_keyboard_only(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, mock_throttle_handler, mock_steering_handler = self._setup_mocks(
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        mock_keyaxis_cls.side_effect = [mock_throttle_handler, mock_steering_handler]
        mock_throttle_handler.update.return_value = 0.8
        mock_steering_handler.update.return_value = -0.5
        mock_gamepad.read_inputs.return_value = None

        mock_pressed_keys = MagicMock()
        mock_pygame.key.get_pressed.return_value = mock_pressed_keys

        input_manager = InputController(self.settings)

        throttle, steering = input_manager.read_inputs()

        mock_pygame.key.get_pressed.assert_called_once()
        mock_throttle_handler.update.assert_called_with(mock_pressed_keys)
        mock_steering_handler.update.assert_called_with(mock_pressed_keys)

        self.assertEqual(throttle, 0.8)
        self.assertEqual(steering, -0.5)

    def test_read_inputs_gamepad_overrides_keyboard(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, mock_throttle_handler, mock_steering_handler = self._setup_mocks(
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        mock_keyaxis_cls.side_effect = [mock_throttle_handler, mock_steering_handler]
        mock_throttle_handler.update.return_value = 0.3
        mock_steering_handler.update.return_value = 0.2

        gamepad_inputs = {
            "steering": 0.9,
            "throttle": 0.7,
            "brake": 0.1
        }
        mock_gamepad.read_inputs.return_value = gamepad_inputs

        input_manager = InputController(self.settings)

        throttle, steering = input_manager.read_inputs()

        self.assertEqual(steering, 0.9)
        self.assertEqual(throttle, 0.6)

    def test_read_inputs_missing_key_handlers(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)

        no_controls_settings = MagicMock()
        no_controls_settings.get.side_effect = lambda key, default=None: {
            "calibrations": {},
            "input": {},
            "controls": {}
        }.get(key, default)

        mock_gamepad.read_inputs.return_value = None

        input_manager = InputController(no_controls_settings)

        with self.assertRaises(KeyError):
            input_manager.read_inputs()

    def test_update_settings_updates_gamepad(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        input_manager = InputController(self.settings)

        mock_gamepad.reset_mock()
        mock_keyaxis_cls.reset_mock()

        new_settings = MagicMock()
        new_settings.get.side_effect = lambda key, default=None: {
            "calibrations": {
                "gamepad1": {"deadzone": 0.2},
                "gamepad2": {"deadzone": 0.15}
            },
            "input": {"guid": "gamepad2"},
            "controls": {
                "keyboard": {
                    "throttle_up": "up",
                    "throttle_down": "down",
                    "steering_right": "right",
                    "steering_left": "left"
                }
            }
        }.get(key, default)

        input_manager.update_settings(new_settings)

        expected_calls = [
            call("gamepad1", {"deadzone": 0.2}),
            call("gamepad2", {"deadzone": 0.15})
        ]
        mock_gamepad.set_calibration.assert_has_calls(expected_calls, any_order=True)
        mock_gamepad.set_active.assert_called_with("gamepad2")
        self.assertTrue(mock_keyaxis_cls.called)

    def test_update_settings_recreates_key_handlers(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)

        initial_throttle = MagicMock()
        initial_steering = MagicMock()
        new_throttle = MagicMock()
        new_steering = MagicMock()

        mock_keyaxis_cls.side_effect = [
            initial_throttle, initial_steering,
            new_throttle, new_steering
        ]

        input_manager = InputController(self.settings)

        self.assertEqual(input_manager.key_handlers["throttle"], initial_throttle)
        self.assertEqual(input_manager.key_handlers["steering"], initial_steering)

        new_settings = MagicMock()
        new_settings.get.side_effect = lambda key, default=None: {
            "calibrations": {},
            "input": {},
            "controls": {
                "keyboard": {
                    "throttle_up": "space",
                    "throttle_down": "shift",
                    "steering_right": "l",
                    "steering_left": "j"
                }
            }
        }.get(key, default)

        input_manager.update_settings(new_settings)

        self.assertEqual(input_manager.key_handlers["throttle"], new_throttle)
        self.assertEqual(input_manager.key_handlers["steering"], new_steering)

        self.assertEqual(mock_keyaxis_cls.call_count, 4)

        last_calls = mock_keyaxis_cls.call_args_list[-2:]

        self.assertEqual(last_calls[0][1]["positive"], "space")
        self.assertEqual(last_calls[0][1]["negative"], "shift")

        self.assertEqual(last_calls[1][1]["positive"], "l")
        self.assertEqual(last_calls[1][1]["negative"], "j")

    def test_update_settings_no_input_guid(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        input_manager = InputController(self.settings)

        mock_gamepad.reset_mock()

        no_guid_settings = MagicMock()
        no_guid_settings.get.side_effect = lambda key, default=None: {
            "calibrations": {"gamepad1": {"deadzone": 0.1}},
            "input": {},
            "controls": {"keyboard": {"throttle_up": "w", "throttle_down": "s", "steering_right": "d", "steering_left": "a"}}
        }.get(key, default)

        input_manager.update_settings(no_guid_settings)

        mock_gamepad.set_active.assert_not_called()
        mock_gamepad.set_calibration.assert_called()

    def test_shutdown_stops_gamepad_manager(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        input_manager = InputController(self.settings)

        input_manager.shutdown()

        mock_gamepad.stop.assert_called_once()

    def test_constants_are_defined(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        self.assertEqual(InputController.THROTTLE_RANGE, (-1.0, 1.0))
        self.assertEqual(InputController.STEERING_RANGE, (-1.0, 1.0))

    def test_gamepad_inputs_with_zero_brake(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, mock_throttle_handler, mock_steering_handler = self._setup_mocks(
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        mock_keyaxis_cls.side_effect = [mock_throttle_handler, mock_steering_handler]

        gamepad_inputs = {
            "steering": 0.5,
            "throttle": 0.8,
            "brake": 0.0
        }
        mock_gamepad.read_inputs.return_value = gamepad_inputs

        input_manager = InputController(self.settings)

        throttle, steering = input_manager.read_inputs()

        self.assertEqual(throttle, 0.8)
        self.assertEqual(steering, 0.5)

    def test_gamepad_inputs_with_full_brake(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, mock_throttle_handler, mock_steering_handler = self._setup_mocks(
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        mock_keyaxis_cls.side_effect = [mock_throttle_handler, mock_steering_handler]

        gamepad_inputs = {
            "steering": -0.3,
            "throttle": 0.6,
            "brake": 1.0
        }
        mock_gamepad.read_inputs.return_value = gamepad_inputs

        input_manager = InputController(self.settings)

        throttle, steering = input_manager.read_inputs()

        self.assertEqual(throttle, -0.4)
        self.assertEqual(steering, -0.3)


if __name__ == '__main__':
    unittest.main()
