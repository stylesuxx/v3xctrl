# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame

from v3xctrl_ui.menu.tabs.InputTab import InputTab


class DummyGamepad:
    def __init__(self, guid, name, id_):
        self.guid = guid
        self.name = name
        self.id = id_
        self.initialized = True

    def get_name(self):
        return self.name

    def get_guid(self):
        return self.guid

    def get_init(self):
        return self.initialized

    def init(self):
        self.initialized = True

    def get_id(self):
        return self.id

    def get_numaxes(self):
        return 2

    def get_axis(self, axis):
        return 0.0


class DummyGamepadManager:
    def __init__(self):
        self.calibrations = {
            "guid-123": {
                "center": [0, 0],
                "scale": [1, 1]
            }
        }
        self._active_guid = "guid-123"
        self.observers = []

    def get_calibrations(self):
        return self.calibrations

    def get_calibration(self, guid):
        return self.calibrations.get(guid)

    def get_selected_guid(self):
        return self._active_guid

    def set_active(self, guid):
        self._active_guid = guid

    def get_gamepads(self):
        return {
            "guid-123": DummyGamepad(guid="guid-123", name="Dummy Gamepad", id_=0)
        }

    def add_observer(self, callback):
        self.observers.append(callback)

    def read_inputs(self):
        return {
            "throttle": 0.0,
            "steering": 0.0
        }


class TestInputTab(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))

        self.settings = {
            "controls": {
                "keyboard": {
                    "forward": 119,  # W
                    "backward": 115  # S
                }
            }
        }

        self.toggle_called = []

        def on_active_toggle(active):
            self.toggle_called.append(active)

        self.manager = DummyGamepadManager()
        self.tab = InputTab(
            settings=self.settings.copy(),
            width=640,
            height=480,
            padding=10,
            y_offset=0,
            gamepad_manager=self.manager,
            on_active_toggle=on_active_toggle
        )

    def test_initial_keyboard_controls_loaded(self):
        key_names = [w.control_name for w in self.tab.key_widgets]
        self.assertIn("forward", key_names)
        self.assertIn("backward", key_names)

    def test_on_control_key_change_updates_settings(self):
        self.tab._on_control_key_change("forward", 97)  # A
        self.assertEqual(self.tab.settings["controls"]["keyboard"]["forward"], 97)

    def test_on_active_toggle_invokes_callback(self):
        self.assertEqual(len(self.toggle_called), 0)
        self.tab._on_active_toggle(True)
        self.assertEqual(self.toggle_called[-1], True)
        self.tab._on_active_toggle(False)
        self.assertEqual(self.toggle_called[-1], False)

    def test_get_settings_returns_expected_structure(self):
        result = self.tab.get_settings()
        self.assertIn("input", result)
        self.assertIn("guid", result["input"])
        self.assertIn("calibrations", result)
        self.assertEqual(result["input"]["guid"], "guid-123")
        self.assertEqual(result["calibrations"], self.manager.get_calibrations())

    def test_draw_does_not_crash(self):
        surface = pygame.Surface((640, 480))
        self.tab.draw(surface)


if __name__ == "__main__":
    unittest.main()
