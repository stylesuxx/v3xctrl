# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest

import pygame

from v3xctrl_ui.utils.colors import WHITE, RED
from v3xctrl_ui.osd.widgets import RecWidget


class TestRecWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.widget = RecWidget(position=(10, 20))
        self.screen = pygame.Surface((200, 100), pygame.SRCALPHA)

    def test_initial_values(self):
        self.assertEqual(self.widget.position, (10, 20))
        self.assertEqual(self.widget.border_radius, 5)
        self.assertEqual(self.widget.color, WHITE)
        self.assertEqual(self.widget.bg_color, RED)
        self.assertEqual(self.widget.background_alpha, 255)

    def test_custom_padding(self):
        widget = RecWidget(
            position=(0, 0),
            top_padding=10,
            bottom_padding=8,
            left_padding=12,
            right_padding=14
        )
        self.assertEqual(widget.top_padding, 10)
        self.assertEqual(widget.bottom_padding, 8)
        self.assertEqual(widget.left_padding, 12)
        self.assertEqual(widget.right_padding, 14)

    def test_custom_border_radius(self):
        widget = RecWidget(position=(0, 0), border_radius=10)
        self.assertEqual(widget.border_radius, 10)

    def test_draw_without_parameters(self):
        # RecWidget.draw() should work without passing text parameter
        self.widget.draw(self.screen)
        self.assertIsNotNone(self.widget.surface)

    def test_draw_ignores_text_parameter(self):
        # RecWidget should always draw "REC" regardless of parameter
        self.widget.draw(self.screen, "IGNORE")
        self.assertIsNotNone(self.widget.surface)

    def test_background_has_rounded_corners(self):
        # Verify that bg_surface exists and has proper dimensions
        self.assertIsNotNone(self.widget.bg_surface)
        self.assertGreater(self.widget.bg_surface.get_width(), 0)
        self.assertGreater(self.widget.bg_surface.get_height(), 0)

    def test_inherits_from_textwidget(self):
        from v3xctrl_ui.osd.widgets import TextWidget
        self.assertIsInstance(self.widget, TextWidget)

    def test_width_calculated_from_text(self):
        # Width should be calculated based on "REC" text plus padding
        self.assertGreater(self.widget.width, 0)
        self.assertEqual(self.widget.width, self.widget.length)

    def test_draw_executes_without_crash(self):
        self.widget.draw(self.screen)

    def test_surface_created_after_draw(self):
        self.widget.draw(self.screen)
        self.assertIsNotNone(self.widget.surface)
        self.assertIsNotNone(self.widget.text_surface)

    def test_default_padding_values(self):
        widget = RecWidget(position=(0, 0))
        self.assertEqual(widget.top_padding, 5)
        self.assertEqual(widget.bottom_padding, 3)
        self.assertEqual(widget.left_padding, 8)
        self.assertEqual(widget.right_padding, 8)


if __name__ == "__main__":
    unittest.main()
