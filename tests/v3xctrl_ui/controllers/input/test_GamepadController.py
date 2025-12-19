import unittest
from unittest.mock import MagicMock, patch

import pygame

from v3xctrl_ui.controllers.input.GamepadController import GamepadController


@patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.init")
class TestGamepadController(unittest.TestCase):
    def setUp(self):
        self.mgr = GamepadController()

    def test_add_observer_and_get_gamepads(self, mock_js_init):
        cb = MagicMock()
        self.mgr.add_observer(cb)
        self.assertIn(cb, self.mgr._observers)
        self.assertEqual(self.mgr.get_gamepads(), {})

    def test_get_gamepad(self, mock_js_init):
        fake_js = MagicMock()
        self.mgr._gamepads["guid1"] = fake_js
        self.assertIs(self.mgr.get_gamepad("guid1"), fake_js)

    def test_calibration_methods(self, mock_js_init):
        self.mgr.set_calibration("g1", {"axis": 0})
        self.assertEqual(self.mgr.get_calibration("g1"), {"axis": 0})
        self.assertIn("g1", self.mgr.get_calibrations())

    def test_set_active_and_unlocked(self, mock_js_init):
        fake_js = MagicMock()
        fake_js.get_init.return_value = False
        self.mgr._gamepads["g1"] = fake_js
        self.mgr._settings["g1"] = {"axis": 0}
        self.mgr.set_active("g1")
        self.assertIs(self.mgr._active_gamepad, fake_js)
        self.assertEqual(self.mgr._active_settings, {"axis": 0})

        self.mgr._set_active_unlocked("g2")
        self.assertIsNone(self.mgr._active_gamepad)

    def test_remap_centered_and_remap(self, mock_js_init):
        self.assertAlmostEqual(self.mgr._remap_centered(5, (0, 5, 10), (-1, 0, 1)), 0)
        self.assertEqual(self.mgr._remap_centered(5, (5, 5, 10), (-1, 0, 1)), 0)

        self.assertAlmostEqual(self.mgr._remap(5, (0, 10), (0, 1)), 0.5)
        self.assertEqual(self.mgr._remap(5, (5, 5), (0, 1)), 0)

    @patch("v3xctrl_ui.controllers.input.GamepadController.clamp", side_effect=lambda v, a, b: v)
    def test_read_inputs_with_center_and_invert(self, mock_clamp, mock_js_init):
        js = MagicMock()
        js.get_init.return_value = True
        js.get_numaxes.return_value = 1
        js.get_axis.return_value = 0.5

        self.mgr._active_gamepad = js
        self.mgr._active_settings = {
            "steering": {
                "axis": 0,
                "invert": True,
                "min": -1.0,
                "max": 1.0,
                "center": 0.0
            }
        }
        values = self.mgr.read_inputs()
        self.assertIn("steering", values)
        self.assertLessEqual(values["steering"], 0)

    @patch("v3xctrl_ui.controllers.input.GamepadController.clamp", side_effect=lambda v, a, b: v)
    def test_read_inputs_without_center(self, mock_clamp, mock_js_init):
        js = MagicMock()
        js.get_init.return_value = True
        js.get_numaxes.return_value = 1
        js.get_axis.return_value = 0.5

        self.mgr._active_gamepad = js
        self.mgr._active_settings = {
            "throttle": {
                "axis": 0,
                "invert": False,
                "min": 0.0,
                "max": 1.0
            }
        }
        values = self.mgr.read_inputs()
        self.assertIn("throttle", values)

    def test_read_inputs_returns_none_when_inactive(self, mock_js_init):
        self.mgr._active_gamepad = None
        self.assertIsNone(self.mgr.read_inputs())

    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.error", new=Exception)
    def test_read_inputs_handles_pygame_error(self, mock_js_init):
        js = MagicMock()
        js.get_init.return_value = True
        js.get_numaxes.return_value = 1
        js.get_axis.side_effect = Exception("pygame.error")
        self.mgr._active_gamepad = js
        self.mgr._active_settings = {
            "axis1": {"axis": 0, "invert": False, "min": 0.0, "max": 1.0}
        }
        self.assertEqual(self.mgr.read_inputs(), {})

    def test_stop_sets_event(self, mock_js_init):
        self.assertFalse(self.mgr._stop_event.is_set())
        self.mgr.stop()
        self.assertTrue(self.mgr._stop_event.is_set())

    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.get_count", return_value=2)
    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.Joystick")
    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.time.wait")
    def test_run_detects_new_gamepads(self, mock_wait, mock_joystick_cls, mock_get_count, mock_js_init):
        mock_js1 = MagicMock()
        mock_js1.get_init.return_value = False
        mock_js1.get_guid.return_value = "guid1"

        mock_js2 = MagicMock()
        mock_js2.get_init.return_value = True
        mock_js2.get_guid.return_value = "guid2"

        mock_joystick_cls.side_effect = [mock_js1, mock_js2]

        observer = MagicMock()
        self.mgr.add_observer(observer)

        # Stop after first iteration
        def stop_after_first(*args):
            self.mgr.stop()
        mock_wait.side_effect = stop_after_first

        self.mgr.run()

        observer.assert_called_once()
        gamepads = observer.call_args[0][0]
        self.assertIn("guid1", gamepads)
        self.assertIn("guid2", gamepads)

    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.get_count", return_value=1)
    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.Joystick")
    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.time.wait")
    def test_run_handles_pygame_error(self, mock_wait, mock_joystick_cls, mock_get_count, mock_js_init):
        mock_joystick_cls.side_effect = pygame.error("Joystick error")

        observer = MagicMock()
        self.mgr.add_observer(observer)

        # Set previous_guids to something different to force observer call
        self.mgr._previous_guids = {"some_old_guid"}

        def stop_after_first(*args):
            self.mgr.stop()
        mock_wait.side_effect = stop_after_first

        self.mgr.run()

        # Observer should be called with empty dict since pygame.error occurred
        observer.assert_called_once_with({})

    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.get_count", return_value=1)
    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.Joystick")
    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.time.wait")
    def test_run_rebinds_active_gamepad(self, mock_wait, mock_joystick_cls, mock_get_count, mock_js_init):
        mock_js = MagicMock()
        mock_js.get_init.return_value = True
        mock_js.get_guid.return_value = "guid1"
        mock_joystick_cls.return_value = mock_js

        # Set up initial state with active gamepad
        self.mgr._active_guid = "guid1"
        self.mgr._active_gamepad = None  # Force rebind
        self.mgr._active_settings = None
        self.mgr._settings["guid1"] = {"axis": 0}

        def stop_after_first(*args):
            self.mgr.stop()
        mock_wait.side_effect = stop_after_first

        self.mgr.run()

        self.assertEqual(self.mgr._active_gamepad, mock_js)
        self.assertEqual(self.mgr._active_settings, {"axis": 0})

    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.get_count", return_value=0)
    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.time.wait")
    def test_run_clears_active_when_gamepad_removed(self, mock_wait, mock_get_count, mock_js_init):
        # Set up initial state with active gamepad
        self.mgr._active_guid = "guid1"
        self.mgr._active_gamepad = MagicMock()
        self.mgr._active_settings = {"axis": 0}
        self.mgr._previous_guids = {"guid1"}

        def stop_after_first(*args):
            self.mgr.stop()
        mock_wait.side_effect = stop_after_first

        self.mgr.run()

        self.assertIsNone(self.mgr._active_gamepad)
        self.assertIsNone(self.mgr._active_settings)

    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.get_count", return_value=1)
    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.joystick.Joystick")
    @patch("v3xctrl_ui.controllers.input.GamepadController.pygame.time.wait")
    def test_run_no_observer_call_when_no_changes(self, mock_wait, mock_joystick_cls, mock_get_count, mock_js_init):
        mock_js = MagicMock()
        mock_js.get_init.return_value = True
        mock_js.get_guid.return_value = "guid1"
        mock_joystick_cls.return_value = mock_js

        # Set previous guids to match current
        self.mgr._previous_guids = {"guid1"}

        observer = MagicMock()
        self.mgr.add_observer(observer)

        iteration_count = 0
        def stop_after_second(*args):
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count >= 2:
                self.mgr.stop()
        mock_wait.side_effect = stop_after_second

        self.mgr.run()

        # Observer should not be called since no changes occurred
        observer.assert_not_called()

    def test_get_gamepad_returns_specific_gamepad(self, mock_js_init):
        mock_js = MagicMock()
        self.mgr._gamepads["guid1"] = mock_js
        self.assertEqual(self.mgr.get_gamepad("guid1"), mock_js)

    def test_get_calibration_returns_empty_for_missing_guid(self, mock_js_init):
        self.assertEqual(self.mgr.get_calibration("nonexistent"), {})

    def test_set_active_unlocked_no_gamepad(self, mock_js_init):
        self.mgr._set_active_unlocked("nonexistent")
        self.assertEqual(self.mgr._active_guid, "nonexistent")
        self.assertIsNone(self.mgr._active_gamepad)
        self.assertIsNone(self.mgr._active_settings)

    def test_set_active_unlocked_no_settings(self, mock_js_init):
        mock_js = MagicMock()
        mock_js.get_init.return_value = True
        self.mgr._gamepads["guid1"] = mock_js

        self.mgr._set_active_unlocked("guid1")
        self.assertEqual(self.mgr._active_guid, "guid1")
        self.assertIsNone(self.mgr._active_gamepad)
        self.assertIsNone(self.mgr._active_settings)

    def test_set_active_unlocked_initializes_gamepad(self, mock_js_init):
        mock_js = MagicMock()
        mock_js.get_init.return_value = False
        self.mgr._gamepads["guid1"] = mock_js
        self.mgr._settings["guid1"] = {"axis": 0}

        self.mgr._set_active_unlocked("guid1")

        self.assertEqual(self.mgr._active_gamepad, mock_js)
        self.assertEqual(self.mgr._active_settings, {"axis": 0})

    def test_read_inputs_gamepad_not_initialized(self, mock_js_init):
        js = MagicMock()
        js.get_init.return_value = False
        self.mgr._active_gamepad = js
        self.mgr._active_settings = {"axis": 0}

        self.assertIsNone(self.mgr.read_inputs())

    def test_read_inputs_axis_out_of_range(self, mock_js_init):
        js = MagicMock()
        js.get_init.return_value = True
        js.get_numaxes.return_value = 2

        self.mgr._active_gamepad = js
        self.mgr._active_settings = {
            "invalid_axis": {"axis": 5, "invert": False, "min": 0.0, "max": 1.0}
        }

        values = self.mgr.read_inputs()
        self.assertEqual(values, {})

    def test_read_inputs_no_axis_config(self, mock_js_init):
        js = MagicMock()
        js.get_init.return_value = True
        js.get_numaxes.return_value = 2

        self.mgr._active_gamepad = js
        self.mgr._active_settings = {
            "no_axis": {"invert": False, "min": 0.0, "max": 1.0}
        }

        values = self.mgr.read_inputs()
        self.assertEqual(values, {})

    @patch("v3xctrl_ui.controllers.input.GamepadController.clamp", side_effect=lambda v, a, b: v)
    def test_read_inputs_with_invert_no_center(self, mock_clamp, mock_js_init):
        js = MagicMock()
        js.get_init.return_value = True
        js.get_numaxes.return_value = 1
        js.get_axis.return_value = 0.3

        self.mgr._active_gamepad = js
        self.mgr._active_settings = {
            "throttle": {
                "axis": 0,
                "invert": True,
                "min": 0.0,
                "max": 1.0
            }
        }

        values = self.mgr.read_inputs()
        # Should use swapped min/max for inverted axis
        self.assertIn("throttle", values)

    def test_remap_centered_value_above_center(self, mock_js_init):
        # Test the else branch in _remap_centered
        result = self.mgr._remap_centered(7, (0, 5, 10), (-1, 0, 1))
        self.assertAlmostEqual(result, 0.4)

    def test_remap_centered_zero_span_above_center(self, mock_js_init):
        # Test zero span in upper range
        result = self.mgr._remap_centered(10, (0, 5, 5), (-1, 0, 1))
        self.assertEqual(result, 0)


if __name__ == '__main__':
    unittest.main()
