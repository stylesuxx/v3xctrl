# Required before importing pygame, otherwise screen might flicker during tests
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
                "battery_percent": {"display": False},
                "signal_quality": {"display": True},
                "signal_band": {"display": False},
                "signal_cell": {"display": True}
            }
        }

        self.tab = OsdTab(self.settings.copy(), width=640, height=480, padding=10, y_offset=0)

    def test_initial_checkbox_states(self):
        self.assertTrue(self.tab.checkboxes["debug"].checked)
        self.assertTrue(self.tab.checkboxes["steering"].checked)
        self.assertFalse(self.tab.checkboxes["throttle"].checked)
        self.assertFalse(self.tab.checkboxes["battery_voltage"].checked)
        self.assertTrue(self.tab.checkboxes["battery_average_voltage"].checked)
        self.assertFalse(self.tab.checkboxes["battery_percent"].checked)
        self.assertTrue(self.tab.checkboxes["signal_quality"].checked)
        self.assertFalse(self.tab.checkboxes["signal_band"].checked)
        self.assertTrue(self.tab.checkboxes["signal_cell"].checked)

    def test_checkbox_updates_settings(self):
        self.tab.checkboxes["debug"].set_checked(False)
        self.assertFalse(self.tab.widgets["debug"]["display"])

        self.tab.checkboxes["steering"].set_checked(False)
        self.assertFalse(self.tab.widgets["steering"]["display"])

        self.tab.checkboxes["throttle"].set_checked(True)
        self.assertTrue(self.tab.widgets["throttle"]["display"])

        self.tab.checkboxes["battery_voltage"].set_checked(True)
        self.assertTrue(self.tab.widgets["battery_voltage"]["display"])

        self.tab.checkboxes["battery_average_voltage"].set_checked(False)
        self.assertFalse(self.tab.widgets["battery_average_voltage"]["display"])

        self.tab.checkboxes["battery_percent"].set_checked(True)
        self.assertTrue(self.tab.widgets["battery_percent"]["display"])

        self.tab.checkboxes["signal_quality"].set_checked(False)
        self.assertFalse(self.tab.widgets["signal_quality"]["display"])

        self.tab.checkboxes["signal_band"].set_checked(True)
        self.assertTrue(self.tab.widgets["signal_band"]["display"])

        self.tab.checkboxes["signal_cell"].set_checked(False)
        self.assertFalse(self.tab.widgets["signal_cell"]["display"])

    def test_get_settings_aggregation(self):
        self.tab.checkboxes["debug"].set_checked(False)
        self.tab.checkboxes["steering"].set_checked(False)
        self.tab.checkboxes["battery_percent"].set_checked(True)

        settings = self.tab.get_settings()

        self.assertFalse(settings["widgets"]["debug"]["display"])
        self.assertFalse(settings["widgets"]["steering"]["display"])
        self.assertTrue(settings["widgets"]["battery_percent"]["display"])

    def test_draw_runs_without_error(self):
        surface = pygame.Surface((640, 480))
        self.tab.draw(surface)


if __name__ == "__main__":
    unittest.main()
