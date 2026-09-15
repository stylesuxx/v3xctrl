# Required before importing pygame, otherwise screen might flicker during tests
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest

import pygame

from v3xctrl_ui.core.StatusLevel import StatusLevel
from v3xctrl_ui.osd.widgets import StatusWidget
from v3xctrl_ui.utils.colors import GREEN, GREY, RED, YELLOW


class TestStatusWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.widget = StatusWidget(position=(0, 0), size=20, label="TEST")
        self.screen = pygame.Surface((200, 100))

    def test_initial_color_is_default(self):
        self.assertEqual(self.widget.color, GREY)

    def test_draw_sets_status_color_warning(self):
        self.widget.draw(self.screen, StatusLevel.WARNING)
        self.assertEqual(self.widget.color, YELLOW)

    def test_draw_sets_status_color_good(self):
        self.widget.draw(self.screen, StatusLevel.GOOD)
        self.assertEqual(self.widget.color, GREEN)

    def test_draw_sets_status_color_bad(self):
        self.widget.draw(self.screen, StatusLevel.BAD)
        self.assertEqual(self.widget.color, RED)

    def test_draw_sets_status_color_neutral(self):
        self.widget.draw(self.screen, StatusLevel.GOOD)
        self.widget.draw(self.screen, StatusLevel.NEUTRAL)
        self.assertEqual(self.widget.color, GREY)

    def test_every_level_has_a_color(self):
        for level in StatusLevel:
            self.assertIn(level, StatusWidget.LEVEL_COLORS)

    def test_draw_executes_without_crash(self):
        self.widget.draw(self.screen, StatusLevel.GOOD)

    def test_draw_extra_is_called(self):
        class ExtendedStatusWidget(StatusWidget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.extra_called = False

            def draw_extra(self, surface):
                self.extra_called = True

        widget = ExtendedStatusWidget((0, 0), 20, "Label")
        screen = pygame.Surface((100, 50))
        widget.draw(screen, StatusLevel.GOOD)
        self.assertTrue(widget.extra_called)


if __name__ == "__main__":
    unittest.main()
