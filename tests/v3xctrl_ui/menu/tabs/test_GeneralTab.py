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
            "relay": {
                "enabled": True,
                "server": "192.168.1.1",
                "id": "relay01"
            },
            "udp_packet_ttl": 100
        }

        self.tab = GeneralTab(self.settings.copy(), width=640, height=480, padding=10, y_offset=0)

    def tearDown(self):
        pygame.quit()

    def test_initial_values_from_settings(self):
        self.assertEqual(self.tab.video_input.get_value(), 5000)
        self.assertEqual(self.tab.control_input.get_value(), 6000)
        self.assertEqual(self.tab.relay_server_input.get_value(), "192.168.1.1")
        self.assertEqual(self.tab.relay_id_input.get_value(), "relay01")
        self.assertEqual(self.tab.udp_packet_ttl_input.get_value(), 100)

    def test_port_change_reflects_in_settings(self):
        self.tab._on_port_change("video", "12345")
        self.assertEqual(self.tab.ports["video"], 12345)

    def test_textinput_updates_settings(self):
        self.tab.relay_server_input.on_change("10.10.10.10")
        self.assertEqual(self.tab.relay["server"], "10.10.10.10")

        self.tab.relay_id_input.on_change("new-id")
        self.assertEqual(self.tab.relay["id"], "new-id")

    def test_udp_packet_ttl_change(self):
        self.tab.udp_packet_ttl_input.on_change("2500")
        self.assertEqual(self.tab.udp_packet_ttl, 2500)

    def test_get_settings_aggregation(self):
        self.tab.video_input.on_change("4242")
        self.tab.udp_packet_ttl_input.on_change("3333")
        settings = self.tab.get_settings()
        self.assertEqual(settings["ports"]["video"], 4242)
        self.assertEqual(settings["udp_packet_ttl"], 3333)

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
