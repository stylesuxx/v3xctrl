import unittest
from unittest.mock import MagicMock, patch
import types

from src.v3xctrl_ui.GamepadManager import GamepadManager


class TestGamepadManager(unittest.TestCase):
    def setUp(self):
        # Patch pygame.joystick.init so it doesn't need real devices
        self.patcher_js_init = patch("src.v3xctrl_ui.GamepadManager.pygame.joystick.init")
        self.mock_js_init = self.patcher_js_init.start()

        self.mgr = GamepadManager()

    def tearDown(self):
        self.patcher_js_init.stop()

    def test_add_observer_and_get_gamepads(self):
        cb = MagicMock()
        self.mgr.add_observer(cb)
        self.assertIn(cb, self.mgr._observers)
        self.assertEqual(self.mgr.get_gamepads(), {})

    def test_get_gamepad(self):
        fake_js = MagicMock()
        self.mgr._gamepads["guid1"] = fake_js
        self.assertIs(self.mgr.get_gamepad("guid1"), fake_js)

    def test_calibration_methods(self):
        self.mgr.set_calibration("g1", {"axis": 0})
        self.assertEqual(self.mgr.get_calibration("g1"), {"axis": 0})
        self.assertIn("g1", self.mgr.get_calibrations())

    def test_set_active_and_unlocked(self):
        fake_js = MagicMock()
        fake_js.get_init.return_value = False
        self.mgr._gamepads["g1"] = fake_js
        self.mgr._settings["g1"] = {"axis": 0}
        self.mgr.set_active("g1")
        self.assertIs(self.mgr._active_gamepad, fake_js)
        self.assertEqual(self.mgr._active_settings, {"axis": 0})

        # no matching js/settings → resets
        self.mgr._set_active_unlocked("g2")
        self.assertIsNone(self.mgr._active_gamepad)

    def test_remap_centered_and_remap(self):
        # Normal centered
        val = self.mgr._remap_centered(5, (0, 5, 10), (-1, 0, 1))
        self.assertAlmostEqual(val, 0)
        # Zero-span path
        val2 = self.mgr._remap_centered(5, (5, 5, 10), (-1, 0, 1))
        self.assertEqual(val2, 0)

        # Normal remap
        r = self.mgr._remap(5, (0, 10), (0, 1))
        self.assertAlmostEqual(r, 0.5)
        # Zero-span path
        r2 = self.mgr._remap(5, (5, 5), (0, 1))
        self.assertEqual(r2, 0)

    @patch("src.v3xctrl_ui.GamepadManager.clamp", side_effect=lambda v, a, b: v)
    def test_read_inputs_with_center_and_invert(self, mock_clamp):
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
        self.assertLessEqual(values["steering"], 0)  # inverted

    @patch("src.v3xctrl_ui.GamepadManager.clamp", side_effect=lambda v, a, b: v)
    def test_read_inputs_without_center(self, mock_clamp):
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

    def test_read_inputs_returns_none_when_inactive(self):
        self.mgr._active_gamepad = None
        self.assertIsNone(self.mgr.read_inputs())

    @patch("src.v3xctrl_ui.GamepadManager.pygame.error", new=Exception)
    def test_read_inputs_handles_pygame_error(self):
        js = MagicMock()
        js.get_init.return_value = True
        js.get_numaxes.return_value = 1
        js.get_axis.side_effect = Exception("pygame.error")
        self.mgr._active_gamepad = js
        self.mgr._active_settings = {
            "axis1": {"axis": 0, "invert": False, "min": 0.0, "max": 1.0}
        }
        vals = self.mgr.read_inputs()
        self.assertEqual(vals, {})

    def test_stop_sets_event(self):
        self.assertFalse(self.mgr._stop_event.is_set())
        self.mgr.stop()
        self.assertTrue(self.mgr._stop_event.is_set())
