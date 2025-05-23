import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame

from v3xctrl_ui.menu.tabs import GeneralTab


class TestGeneralTab(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))

        self.settings = {
            "ports": {"video": 5000, "control": 6000},
            "widgets": {
                "steering": {"display": True},
                "throttle": {"display": False}
            },
            "debug": True,
            "relay": {
                "enabled": True,
                "server": "192.168.1.1",
                "id": "relay01"
            }
        }

        self.tab = GeneralTab(self.settings.copy(), width=640, height=480, padding=10, y_offset=0)

    def tearDown(self):
        pygame.quit()

    def test_initial_values_from_settings(self):
        self.assertEqual(self.tab.video_input.get_value(), 5000)
        self.assertEqual(self.tab.control_input.get_value(), 6000)
        self.assertEqual(self.tab.relay_server_input.get_value(), "192.168.1.1")
        self.assertEqual(self.tab.relay_id_input.get_value(), "relay01")
        self.assertTrue(self.tab.debug_checkbox.checked)
        self.assertTrue(self.tab.steering_checkbox.checked)
        self.assertFalse(self.tab.throttle_checkbox.checked)

    def test_port_change_reflects_in_settings(self):
        self.tab._on_port_change("video", "12345")
        self.assertEqual(self.tab.ports["video"], 12345)

    def test_checkbox_updates_settings(self):
        self.tab.debug_checkbox.set_checked(False)
        self.assertFalse(self.tab.debug)

        self.tab.steering_checkbox.set_checked(False)
        self.assertFalse(self.tab.widgets["steering"]["display"])

        self.tab.throttle_checkbox.set_checked(True)
        self.assertTrue(self.tab.widgets["throttle"]["display"])

    def test_textinput_updates_settings(self):
        self.tab.relay_server_input.on_change("10.10.10.10")
        self.assertEqual(self.tab.relay["server"], "10.10.10.10")

        self.tab.relay_id_input.on_change("new-id")
        self.assertEqual(self.tab.relay["id"], "new-id")

    def test_get_settings_aggregation(self):
        self.tab.debug_checkbox.set_checked(False)
        self.tab.video_input.on_change("4242")
        settings = self.tab.get_settings()
        self.assertEqual(settings["debug"], False)
        self.assertEqual(settings["ports"]["video"], 4242)

    def test_draw_runs_without_error(self):
        surface = pygame.Surface((640, 480))
        try:
            self.tab.draw(surface)
        except Exception as e:
            self.fail(f"Draw method raised an exception: {e}")

    def test_on_relay_enable_change_direct(self):
        self.assertTrue(self.tab.relay["enabled"])
        self.tab._on_relay_enable_change(False)
        self.assertFalse(self.tab.relay["enabled"])


if __name__ == "__main__":
    unittest.main()
