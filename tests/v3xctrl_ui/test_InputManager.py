import unittest
from unittest.mock import MagicMock, patch, call

from src.v3xctrl_ui.InputManager import InputManager


class TestInputManager(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures with proper mocking."""
        # Patch GamepadManager
        self.gamepad_patcher = patch("src.v3xctrl_ui.InputManager.GamepadManager")
        self.mock_gamepad_cls = self.gamepad_patcher.start()
        self.mock_gamepad = MagicMock()
        self.mock_gamepad_cls.return_value = self.mock_gamepad

        # Patch KeyAxisHandler
        self.keyaxis_patcher = patch("src.v3xctrl_ui.InputManager.KeyAxisHandler")
        self.mock_keyaxis_cls = self.keyaxis_patcher.start()
        self.mock_throttle_handler = MagicMock()
        self.mock_steering_handler = MagicMock()

        # Patch pygame
        self.pygame_patcher = patch("src.v3xctrl_ui.InputManager.pygame")
        self.mock_pygame = self.pygame_patcher.start()

        # Mock settings
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

    def tearDown(self):
        """Clean up patches."""
        self.gamepad_patcher.stop()
        self.keyaxis_patcher.stop()
        self.pygame_patcher.stop()

    def test_initialization_creates_components(self):
        """Test that InputManager properly initializes all components."""
        # Setup KeyAxisHandler mock to return different instances
        self.mock_keyaxis_cls.side_effect = [self.mock_throttle_handler, self.mock_steering_handler]

        input_manager = InputManager(self.settings)

        # Verify GamepadManager was created and started
        self.mock_gamepad_cls.assert_called_once()
        self.mock_gamepad.set_calibration.assert_called_with("gamepad1", {"deadzone": 0.1})
        self.mock_gamepad.set_active.assert_called_with("gamepad1")
        self.mock_gamepad.start.assert_called_once()

        # Verify KeyAxisHandler was created for both throttle and steering
        self.assertEqual(self.mock_keyaxis_cls.call_count, 2)

        # Verify throttle handler setup
        throttle_call = self.mock_keyaxis_cls.call_args_list[0]
        self.assertEqual(throttle_call[1]["positive"], "w")
        self.assertEqual(throttle_call[1]["negative"], "s")
        self.assertEqual(throttle_call[1]["min_val"], -1.0)
        self.assertEqual(throttle_call[1]["max_val"], 1.0)

        # Verify steering handler setup
        steering_call = self.mock_keyaxis_cls.call_args_list[1]
        self.assertEqual(steering_call[1]["positive"], "d")
        self.assertEqual(steering_call[1]["negative"], "a")
        self.assertEqual(steering_call[1]["min_val"], -1.0)
        self.assertEqual(steering_call[1]["max_val"], 1.0)

    def test_initialization_no_keyboard_controls(self):
        """Test initialization when no keyboard controls are configured."""
        no_controls_settings = MagicMock()
        no_controls_settings.get.side_effect = lambda key, default=None: {
            "calibrations": {},
            "input": {},
            "controls": {}
        }.get(key, default)

        input_manager = InputManager(no_controls_settings)

        # Should still create gamepad manager but no key handlers
        self.mock_gamepad_cls.assert_called_once()
        self.assertEqual(len(input_manager.key_handlers), 0)

    def test_read_inputs_keyboard_only(self):
        """Test reading inputs with keyboard only."""
        # Setup mocks
        self.mock_keyaxis_cls.side_effect = [self.mock_throttle_handler, self.mock_steering_handler]
        self.mock_throttle_handler.update.return_value = 0.8
        self.mock_steering_handler.update.return_value = -0.5
        self.mock_gamepad.read_inputs.return_value = None

        mock_pressed_keys = MagicMock()
        self.mock_pygame.key.get_pressed.return_value = mock_pressed_keys

        input_manager = InputManager(self.settings)

        throttle, steering = input_manager.read_inputs()

        # Verify keyboard inputs were read
        self.mock_pygame.key.get_pressed.assert_called_once()
        self.mock_throttle_handler.update.assert_called_with(mock_pressed_keys)
        self.mock_steering_handler.update.assert_called_with(mock_pressed_keys)

        # Verify returned values
        self.assertEqual(throttle, 0.8)
        self.assertEqual(steering, -0.5)

    def test_read_inputs_gamepad_overrides_keyboard(self):
        """Test that gamepad inputs override keyboard inputs."""
        # Setup mocks
        self.mock_keyaxis_cls.side_effect = [self.mock_throttle_handler, self.mock_steering_handler]
        self.mock_throttle_handler.update.return_value = 0.3
        self.mock_steering_handler.update.return_value = 0.2

        # Mock gamepad inputs
        gamepad_inputs = {
            "steering": 0.9,
            "throttle": 0.7,
            "brake": 0.1
        }
        self.mock_gamepad.read_inputs.return_value = gamepad_inputs

        input_manager = InputManager(self.settings)

        throttle, steering = input_manager.read_inputs()

        # Gamepad should override keyboard
        self.assertEqual(steering, 0.9)  # Direct from gamepad
        self.assertEqual(throttle, 0.6)  # throttle - brake = 0.7 - 0.1

    def test_read_inputs_missing_key_handlers(self):
        """Test reading inputs when key handlers are missing."""
        # Create InputManager with no keyboard controls
        no_controls_settings = MagicMock()
        no_controls_settings.get.side_effect = lambda key, default=None: {
            "calibrations": {},
            "input": {},
            "controls": {}
        }.get(key, default)

        self.mock_gamepad.read_inputs.return_value = None

        input_manager = InputManager(no_controls_settings)

        # This should raise KeyError without proper error handling
        with self.assertRaises(KeyError):
            input_manager.read_inputs()

    def test_update_settings_updates_gamepad(self):
        """Test that update_settings properly updates gamepad configuration."""
        input_manager = InputManager(self.settings)

        # Reset mocks
        self.mock_gamepad.reset_mock()
        self.mock_keyaxis_cls.reset_mock()

        # New settings
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

        # Verify gamepad calibrations were updated
        expected_calls = [
            call("gamepad1", {"deadzone": 0.2}),
            call("gamepad2", {"deadzone": 0.15})
        ]
        self.mock_gamepad.set_calibration.assert_has_calls(expected_calls, any_order=True)

        # Verify active gamepad was updated
        self.mock_gamepad.set_active.assert_called_with("gamepad2")

        # Verify new key handlers were created
        self.assertTrue(self.mock_keyaxis_cls.called)

    def test_update_settings_recreates_key_handlers(self):
        """Test that update_settings recreates key handlers with new keys."""
        # Setup initial KeyAxisHandler mocks
        initial_throttle = MagicMock()
        initial_steering = MagicMock()
        new_throttle = MagicMock()
        new_steering = MagicMock()

        self.mock_keyaxis_cls.side_effect = [
            initial_throttle, initial_steering,  # Initial creation
            new_throttle, new_steering           # Recreation after update
        ]

        input_manager = InputManager(self.settings)

        # Verify initial handlers are in place
        self.assertEqual(input_manager.key_handlers["throttle"], initial_throttle)
        self.assertEqual(input_manager.key_handlers["steering"], initial_steering)

        # Update with new key mappings
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

        # Verify new handlers were created
        self.assertEqual(input_manager.key_handlers["throttle"], new_throttle)
        self.assertEqual(input_manager.key_handlers["steering"], new_steering)

        # Verify new KeyAxisHandlers were created with new key mappings
        self.assertEqual(self.mock_keyaxis_cls.call_count, 4)

        # Check the last two calls (for update_settings)
        last_calls = self.mock_keyaxis_cls.call_args_list[-2:]

        # Throttle handler with new keys
        self.assertEqual(last_calls[0][1]["positive"], "space")
        self.assertEqual(last_calls[0][1]["negative"], "shift")

        # Steering handler with new keys
        self.assertEqual(last_calls[1][1]["positive"], "l")
        self.assertEqual(last_calls[1][1]["negative"], "j")

    def test_update_settings_no_input_guid(self):
        """Test update_settings when no gamepad GUID is specified."""
        input_manager = InputManager(self.settings)

        # Reset mocks
        self.mock_gamepad.reset_mock()

        # Settings without input guid
        no_guid_settings = MagicMock()
        no_guid_settings.get.side_effect = lambda key, default=None: {
            "calibrations": {"gamepad1": {"deadzone": 0.1}},
            "input": {},  # No guid
            "controls": {"keyboard": {"throttle_up": "w", "throttle_down": "s", "steering_right": "d", "steering_left": "a"}}
        }.get(key, default)

        input_manager.update_settings(no_guid_settings)

        # set_active should not be called
        self.mock_gamepad.set_active.assert_not_called()

        # But calibrations should still be set
        self.mock_gamepad.set_calibration.assert_called()

    def test_shutdown_stops_gamepad_manager(self):
        """Test that shutdown properly stops the gamepad manager."""
        input_manager = InputManager(self.settings)

        input_manager.shutdown()

        self.mock_gamepad.stop.assert_called_once()

    def test_constants_are_defined(self):
        """Test that input range constants are properly defined."""
        self.assertEqual(InputManager.THROTTLE_RANGE, (-1.0, 1.0))
        self.assertEqual(InputManager.STEERING_RANGE, (-1.0, 1.0))

    def test_gamepad_inputs_with_zero_brake(self):
        """Test gamepad inputs when brake is zero."""
        # Setup mocks
        self.mock_keyaxis_cls.side_effect = [self.mock_throttle_handler, self.mock_steering_handler]

        gamepad_inputs = {
            "steering": 0.5,
            "throttle": 0.8,
            "brake": 0.0
        }
        self.mock_gamepad.read_inputs.return_value = gamepad_inputs

        input_manager = InputManager(self.settings)

        throttle, steering = input_manager.read_inputs()

        # Throttle should equal throttle input when brake is zero
        self.assertEqual(throttle, 0.8)
        self.assertEqual(steering, 0.5)

    def test_gamepad_inputs_with_full_brake(self):
        """Test gamepad inputs when brake is at maximum."""
        # Setup mocks
        self.mock_keyaxis_cls.side_effect = [self.mock_throttle_handler, self.mock_steering_handler]

        gamepad_inputs = {
            "steering": -0.3,
            "throttle": 0.6,
            "brake": 1.0
        }
        self.mock_gamepad.read_inputs.return_value = gamepad_inputs

        input_manager = InputManager(self.settings)

        throttle, steering = input_manager.read_inputs()

        # Throttle should be negative when brake exceeds throttle
        self.assertEqual(throttle, -0.4)  # 0.6 - 1.0 = -0.4
        self.assertEqual(steering, -0.3)


if __name__ == '__main__':
    unittest.main()
