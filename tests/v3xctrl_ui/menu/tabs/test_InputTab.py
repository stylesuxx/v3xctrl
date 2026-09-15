# Required before importing pygame, otherwise screen might flicker during tests
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest

import pygame

from tests.v3xctrl_ui.settings_helper import build_settings
from v3xctrl_ui.core.SettingsSchema import ControlSettings, KeyboardControls
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
        self.calibrations = {"guid-123": {"center": [0, 0], "scale": [1, 1]}}
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

    def get_active(self):
        return self._active_guid

    def get_gamepads(self):
        return {"guid-123": DummyGamepad(guid="guid-123", name="Dummy Gamepad", id_=0)}

    def add_observer(self, callback):
        self.observers.append(callback)

    def read_inputs(self, apply_deadband: bool = True):
        return {"throttle": 0.0, "steering": 0.0}


class TestInputTab(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))

        self.settings = build_settings(
            controls=ControlSettings(keyboard=KeyboardControls(throttle_up=pygame.K_w, throttle_down=pygame.K_s))
        )

        self.toggle_called = []

        def on_active_toggle(active):
            self.toggle_called.append(active)

        self.manager = DummyGamepadManager()
        self.tab = InputTab(
            settings=self.settings,
            width=640,
            height=480,
            padding=10,
            y_offset=0,
            gamepad_manager=self.manager,
            on_active_toggle=on_active_toggle,
        )

    def test_initial_keyboard_controls_loaded(self):
        key_names = [w.control_name for w in self.tab.key_widgets]
        self.assertIn("throttle_up", key_names)
        self.assertIn("throttle_down", key_names)
        self.assertIn("rec_toggle", key_names)

    def test_on_control_key_change_edits_the_tabs_own_copy(self):
        self.tab._on_control_key_change("throttle_up", pygame.K_a)

        self.assertEqual(self.tab.controls.keyboard.throttle_up, pygame.K_a)
        self.assertEqual(self.settings.controls.keyboard.throttle_up, pygame.K_w)

    def test_rebound_key_is_handed_back_for_saving(self):
        """Rebinding has no other persistence path, so get_settings must carry it."""
        self.tab._on_control_key_change("throttle_up", pygame.K_a)

        self.assertEqual(self.tab.get_settings()["controls"].keyboard.throttle_up, pygame.K_a)

    def test_apply_settings_discards_uncommitted_rebinds(self):
        self.tab._on_control_key_change("throttle_up", pygame.K_a)

        self.tab.apply_settings()

        self.assertEqual(self.tab.controls.keyboard.throttle_up, pygame.K_w)

    def test_on_active_toggle_invokes_callback(self):
        self.assertEqual(len(self.toggle_called), 0)
        self.tab._on_active_toggle(True)
        self.assertEqual(self.toggle_called[-1], True)
        self.tab._on_active_toggle(False)
        self.assertEqual(self.toggle_called[-1], False)

    def test_get_settings_returns_expected_structure(self):
        result = self.tab.get_settings()
        self.assertIn("input", result)
        self.assertIn("calibrations", result)
        self.assertEqual(result["input"].guid, "guid-123")
        self.assertEqual(result["calibrations"].by_guid, self.manager.get_calibrations())

    def test_draw_does_not_crash(self):
        surface = pygame.Surface((640, 480))
        self.tab.draw(surface)

    def test_update_dimensions_rebuilds_columns(self):
        """Test that update_dimensions properly rebuilds column layout"""
        # Get initial column count and check widget column widths
        initial_columns = len(self.tab.keyboard_columns)
        self.assertGreater(initial_columns, 0)

        # Get initial column width for first widget (if exists)
        if len(self.tab.key_widgets) > 0:
            # Store reference to a widget
            first_widget = self.tab.key_widgets[0]

            # Update to a much larger width
            new_width = 1920
            new_height = 1080
            self.tab.update_dimensions(new_width, new_height)

            # Verify dimensions were updated
            self.assertEqual(self.tab.width, new_width)
            self.assertEqual(self.tab.height, new_height)

            # Verify columns were rebuilt
            self.assertEqual(len(self.tab.keyboard_columns), initial_columns)

            # Verify the widget is still in a column
            widget_found = False
            for column in self.tab.keyboard_columns:
                if first_widget in column.widgets:
                    widget_found = True
                    break
            self.assertTrue(widget_found, "Widget should be in a column after resize")


if __name__ == "__main__":
    unittest.main()
