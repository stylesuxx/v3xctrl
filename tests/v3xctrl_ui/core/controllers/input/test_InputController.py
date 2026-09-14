import unittest
from unittest.mock import MagicMock, call, patch

import pygame

from tests.v3xctrl_ui.settings_helper import build_settings
from v3xctrl_ui.core.controllers.input.InputController import InputController
from v3xctrl_ui.core.SettingsSchema import (
    CalibrationSettings,
    ControlSettings,
    InputSettings,
    KeyboardControls,
)


@patch("v3xctrl_ui.core.controllers.input.InputController.GamepadController")
@patch("v3xctrl_ui.core.controllers.input.InputController.KeyAxisHandler")
@patch("v3xctrl_ui.core.controllers.input.InputController.pygame")
class TestInputController(unittest.TestCase):
    def setUp(self):
        self.settings = build_settings(
            calibrations=CalibrationSettings(by_guid={"gamepad1": {"deadzone": 0.1}}),
            input=InputSettings(guid="gamepad1"),
            controls=ControlSettings(keyboard=KeyboardControls()),
        )

    def _setup_mocks(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad = MagicMock()
        mock_gamepad_cls.return_value = mock_gamepad

        mock_throttle_handler = MagicMock()
        mock_steering_handler = MagicMock()

        return mock_gamepad, mock_throttle_handler, mock_steering_handler

    def test_initialization_creates_components(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, mock_throttle_handler, mock_steering_handler = self._setup_mocks(
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls
        )
        mock_keyaxis_cls.side_effect = [mock_throttle_handler, mock_steering_handler]

        _input_manager = InputController(self.settings)

        mock_gamepad_cls.assert_called_once()
        mock_gamepad.set_calibration.assert_called_with("gamepad1", {"deadzone": 0.1})
        mock_gamepad.set_active.assert_called_with("gamepad1")
        mock_gamepad.start.assert_called_once()

        self.assertEqual(mock_keyaxis_cls.call_count, 2)

        throttle_call = mock_keyaxis_cls.call_args_list[0]
        self.assertEqual(throttle_call[1]["positive"], pygame.K_w)
        self.assertEqual(throttle_call[1]["negative"], pygame.K_s)
        self.assertEqual(throttle_call[1]["min_val"], -1.0)
        self.assertEqual(throttle_call[1]["max_val"], 1.0)

        steering_call = mock_keyaxis_cls.call_args_list[1]
        self.assertEqual(steering_call[1]["positive"], pygame.K_d)
        self.assertEqual(steering_call[1]["negative"], pygame.K_a)
        self.assertEqual(steering_call[1]["min_val"], -1.0)
        self.assertEqual(steering_call[1]["max_val"], 1.0)

    def test_a_config_without_controls_falls_back_to_the_default_bindings(
        self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls
    ):
        _mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)

        input_manager = InputController(build_settings())

        mock_gamepad_cls.assert_called_once()
        self.assertEqual(set(input_manager.key_handlers), {"throttle", "steering"})

    def test_read_inputs_keyboard_only(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, mock_throttle_handler, mock_steering_handler = self._setup_mocks(
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls
        )
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
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls
        )
        mock_keyaxis_cls.side_effect = [mock_throttle_handler, mock_steering_handler]
        mock_throttle_handler.update.return_value = 0.3
        mock_steering_handler.update.return_value = 0.2

        gamepad_inputs = {"steering": 0.9, "throttle": 0.7, "brake": 0.1}
        mock_gamepad.read_inputs.return_value = gamepad_inputs

        input_manager = InputController(self.settings)

        throttle, steering = input_manager.read_inputs()

        self.assertEqual(steering, 0.9)
        self.assertEqual(throttle, 0.6)

    def test_read_inputs_missing_key_handlers(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        mock_gamepad.read_inputs.return_value = None

        input_manager = InputController(build_settings())

        self.assertEqual(set(input_manager.key_handlers), {"throttle", "steering"})

    def test_apply_settings_updates_gamepad(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        input_manager = InputController(self.settings)

        mock_gamepad.reset_mock()
        mock_keyaxis_cls.reset_mock()

        new_settings = build_settings(
            calibrations=CalibrationSettings(by_guid={"gamepad1": {"deadzone": 0.2}, "gamepad2": {"deadzone": 0.15}}),
            input=InputSettings(guid="gamepad2"),
            controls=ControlSettings(keyboard=KeyboardControls(throttle_up=pygame.K_UP, throttle_down=pygame.K_DOWN)),
        )

        input_manager.apply_settings(new_settings)

        expected_calls = [call("gamepad1", {"deadzone": 0.2}), call("gamepad2", {"deadzone": 0.15})]
        mock_gamepad.set_calibration.assert_has_calls(expected_calls, any_order=True)
        mock_gamepad.set_active.assert_called_with("gamepad2")
        self.assertTrue(mock_keyaxis_cls.called)

    def test_apply_settings_recreates_key_handlers(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        _mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)

        initial_throttle = MagicMock()
        initial_steering = MagicMock()
        new_throttle = MagicMock()
        new_steering = MagicMock()

        mock_keyaxis_cls.side_effect = [initial_throttle, initial_steering, new_throttle, new_steering]

        input_manager = InputController(self.settings)

        self.assertEqual(input_manager.key_handlers["throttle"], initial_throttle)
        self.assertEqual(input_manager.key_handlers["steering"], initial_steering)

        new_settings = build_settings(
            controls=ControlSettings(
                keyboard=KeyboardControls(
                    throttle_up=pygame.K_SPACE,
                    throttle_down=pygame.K_LSHIFT,
                    steering_right=pygame.K_l,
                    steering_left=pygame.K_j,
                )
            )
        )

        input_manager.apply_settings(new_settings)

        self.assertEqual(input_manager.key_handlers["throttle"], new_throttle)
        self.assertEqual(input_manager.key_handlers["steering"], new_steering)

        self.assertEqual(mock_keyaxis_cls.call_count, 4)

        last_calls = mock_keyaxis_cls.call_args_list[-2:]

        self.assertEqual(last_calls[0][1]["positive"], pygame.K_SPACE)
        self.assertEqual(last_calls[0][1]["negative"], pygame.K_LSHIFT)

        self.assertEqual(last_calls[1][1]["positive"], pygame.K_l)
        self.assertEqual(last_calls[1][1]["negative"], pygame.K_j)

    def test_apply_settings_no_input_guid(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, _, _ = self._setup_mocks(mock_pygame, mock_keyaxis_cls, mock_gamepad_cls)
        input_manager = InputController(self.settings)

        mock_gamepad.reset_mock()

        no_guid_settings = build_settings(
            calibrations=CalibrationSettings(by_guid={"gamepad1": {"deadzone": 0.1}}),
            input=InputSettings(guid=""),
        )

        input_manager.apply_settings(no_guid_settings)

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
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls
        )
        mock_keyaxis_cls.side_effect = [mock_throttle_handler, mock_steering_handler]

        gamepad_inputs = {"steering": 0.5, "throttle": 0.8, "brake": 0.0}
        mock_gamepad.read_inputs.return_value = gamepad_inputs

        input_manager = InputController(self.settings)

        throttle, steering = input_manager.read_inputs()

        self.assertEqual(throttle, 0.8)
        self.assertEqual(steering, 0.5)

    def test_gamepad_inputs_with_full_brake(self, mock_pygame, mock_keyaxis_cls, mock_gamepad_cls):
        mock_gamepad, mock_throttle_handler, mock_steering_handler = self._setup_mocks(
            mock_pygame, mock_keyaxis_cls, mock_gamepad_cls
        )
        mock_keyaxis_cls.side_effect = [mock_throttle_handler, mock_steering_handler]

        gamepad_inputs = {"steering": -0.3, "throttle": 0.6, "brake": 1.0}
        mock_gamepad.read_inputs.return_value = gamepad_inputs

        input_manager = InputController(self.settings)

        throttle, steering = input_manager.read_inputs()

        self.assertEqual(throttle, -0.4)
        self.assertEqual(steering, -0.3)


if __name__ == "__main__":
    unittest.main()
