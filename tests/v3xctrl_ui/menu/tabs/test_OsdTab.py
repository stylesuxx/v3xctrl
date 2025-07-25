import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame

from v3xctrl_ui.menu.tabs import OsdTab


class TestOsdTab(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))

        self.settings = {
            "widgets": {
                "debug": {"display": True},
                "steering": {"display": True},
                "throttle": {"display": False},
                "battery_voltage": {"display": False},
                "battery_average_voltage": {"display": True},
                "battery_percent": {"display": False}
            }
        }

        self.tab = OsdTab(self.settings.copy(), width=640, height=480, padding=10, y_offset=0)

    def tearDown(self):
        pygame.quit()

    def test_initial_checkbox_states(self):
        self.assertTrue(self.tab.debug_checkbox.checked)
        self.assertTrue(self.tab.steering_checkbox.checked)
        self.assertFalse(self.tab.throttle_checkbox.checked)
        self.assertFalse(self.tab.battery_voltage_checkbox.checked)
        self.assertTrue(self.tab.battery_average_voltage_checkbox.checked)
        self.assertFalse(self.tab.battery_percent_checkbox.checked)

    def test_checkbox_updates_settings(self):
        self.tab.debug_checkbox.set_checked(False)
        self.assertFalse(self.tab.widgets["debug"]["display"])

        self.tab.steering_checkbox.set_checked(False)
        self.assertFalse(self.tab.widgets["steering"]["display"])

        self.tab.throttle_checkbox.set_checked(True)
        self.assertTrue(self.tab.widgets["throttle"]["display"])

        self.tab.battery_voltage_checkbox.set_checked(True)
        self.assertTrue(self.tab.widgets["battery_voltage"]["display"])

        self.tab.battery_average_voltage_checkbox.set_checked(False)
        self.assertFalse(self.tab.widgets["battery_average_voltage"]["display"])

        self.tab.battery_percent_checkbox.set_checked(True)
        self.assertTrue(self.tab.widgets["battery_percent"]["display"])

    def test_get_settings_aggregation(self):
        self.tab.debug_checkbox.set_checked(False)
        self.tab.steering_checkbox.set_checked(False)
        self.tab.battery_percent_checkbox.set_checked(True)

        settings = self.tab.get_settings()
        self.assertFalse(settings["widgets"]["debug"]["display"])
        self.assertFalse(settings["widgets"]["steering"]["display"])
        self.assertTrue(settings["widgets"]["battery_percent"]["display"])

    def test_draw_runs_without_error(self):
        surface = pygame.Surface((640, 480))
        try:
            self.tab.draw(surface)
        except Exception as e:
            self.fail(f"Draw method raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()
