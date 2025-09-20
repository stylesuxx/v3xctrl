# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame

from v3xctrl_ui.menu.tabs.FrequenciesTab import FrequenciesTab


class TestFrequenciesTab(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.settings = {
            "timing": {
                "main_loop_fps": 60,
                "control_update_hz": 30,
                "latency_check_hz": 10
            }
        }
        self.tab = FrequenciesTab(self.settings.copy(), width=640, height=480, padding=10, y_offset=0)

    def test_initial_values_from_settings(self):
        self.assertEqual(self.tab.video_input.get_value(), 60)
        self.assertEqual(self.tab.control_input.get_value(), 30)
        self.assertEqual(self.tab.latency_input.get_value(), 10)

    def test_on_rate_change_direct(self):
        self.tab._on_rate_change("main_loop_fps", "75")
        self.assertEqual(self.tab.timing["main_loop_fps"], 75)

    def test_input_updates_timing_settings(self):
        self.tab.control_input.on_change("40")
        self.assertEqual(self.tab.timing["control_update_hz"], 40)

    def test_get_settings(self):
        self.tab.latency_input.on_change("15")
        self.assertEqual(self.tab.get_settings()["timing"]["latency_check_hz"], 15)

    def test_draw_does_not_crash(self):
        surface = pygame.Surface((640, 480))
        try:
            self.tab.draw(surface)
        except Exception as e:
            self.fail(f"Draw raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()
