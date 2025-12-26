# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest

import pygame

from v3xctrl_ui.utils.colors import WHITE, GREY
from v3xctrl_ui.osd.widgets import TextWidget


class TestTextWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.widget = TextWidget(position=(10, 20), length=100)
        self.screen = pygame.Surface((200, 100), pygame.SRCALPHA)

    def test_initial_values(self):
        self.assertEqual(self.widget.position, (10, 20))
        self.assertEqual(self.widget.length, 100)

    def test_draw_sets_surface_and_text_rect(self):
        self.widget.draw(self.screen, "Test")
        self.assertIsNotNone(self.widget.surface)
        self.assertGreater(self.widget.surface.get_height(), 0)
        self.assertEqual(self.widget.surface.get_width(), self.widget.length)
        self.assertIsNotNone(self.widget.text_surface)
        self.assertGreater(self.widget.text_rect.width, 0)
        self.assertGreater(self.widget.height, 0)

    def test_draw_executes_without_crash(self):
        self.widget.draw(self.screen, "Draw safely")

    def test_text_is_centered(self):
        dummy_surface = pygame.Surface((40, 10), pygame.SRCALPHA)
        dummy_rect = pygame.Rect(0, 0, 40, 10)

        class DummyFont:
            def render(self, text, color):
                return dummy_surface, dummy_rect

        self.widget.font = DummyFont()

        self.widget.draw(self.screen, "Centered")
        expected_x = (self.widget.length - 40) // 2
        expected_y = self.widget.top_padding

        self.assertNotEqual(self.widget.surface.get_at((expected_x + 1, expected_y + 1)).a, 0)

    def test_set_alignment(self):
        from v3xctrl_ui.osd.widgets.TextWidget import Alignment

        self.widget.set_alignment(Alignment.LEFT)
        self.assertEqual(self.widget.alignment, Alignment.LEFT)

        self.widget.set_alignment(Alignment.RIGHT)
        self.assertEqual(self.widget.alignment, Alignment.RIGHT)

        self.widget.set_alignment(Alignment.CENTER)
        self.assertEqual(self.widget.alignment, Alignment.CENTER)

    def test_set_text_color(self):
        new_color = (255, 0, 0)
        self.widget.set_text_color(new_color)
        self.assertEqual(self.widget.color, new_color)

    def test_left_alignment(self):
        from v3xctrl_ui.osd.widgets.TextWidget import Alignment

        self.widget.set_alignment(Alignment.LEFT)
        self.widget.draw(self.screen, "Left")

        # Verify text is positioned at left_padding
        dummy_surface = pygame.Surface((40, 10), pygame.SRCALPHA)
        dummy_rect = pygame.Rect(0, 0, 40, 10)

        class DummyFont:
            def render(self, text, color):
                return dummy_surface, dummy_rect

        self.widget.font = DummyFont()
        self.widget.draw(self.screen, "Left")

        # Text should be at left_padding position
        expected_x = self.widget.left_padding
        self.assertNotEqual(self.widget.surface.get_at((expected_x + 1, self.widget.top_padding + 1)).a, 0)

    def test_right_alignment(self):
        from v3xctrl_ui.osd.widgets.TextWidget import Alignment

        self.widget.set_alignment(Alignment.RIGHT)

        dummy_surface = pygame.Surface((40, 10), pygame.SRCALPHA)
        dummy_rect = pygame.Rect(0, 0, 40, 10)

        class DummyFont:
            def render(self, text, color):
                return dummy_surface, dummy_rect

        self.widget.font = DummyFont()
        self.widget.draw(self.screen, "Right")

        # Text should be positioned from the right edge minus text width and right padding
        expected_x = self.widget.length - 40 - self.widget.right_padding
        self.assertNotEqual(self.widget.surface.get_at((expected_x + 1, self.widget.top_padding + 1)).a, 0)

    def test_custom_padding_initialization(self):
        widget = TextWidget(
            position=(0, 0),
            length=200,
            top_padding=10,
            bottom_padding=15,
            left_padding=8,
            right_padding=12
        )

        self.assertEqual(widget.top_padding, 10)
        self.assertEqual(widget.bottom_padding, 15)
        self.assertEqual(widget.left_padding, 8)
        self.assertEqual(widget.right_padding, 12)

    def test_alignment_enum_values(self):
        from v3xctrl_ui.osd.widgets.TextWidget import Alignment

        self.assertEqual(Alignment.LEFT.value, "left")
        self.assertEqual(Alignment.RIGHT.value, "right")
        self.assertEqual(Alignment.CENTER.value, "center")

    def test_set_background_color_with_default_alpha(self):
        new_color = (255, 0, 0)
        self.widget.set_background_color(new_color)
        self.assertEqual(self.widget.bg_color, new_color)
        self.assertEqual(self.widget.background_alpha, 180)
        self.assertIsNotNone(self.widget.bg_surface)

    def test_set_background_color_with_custom_alpha(self):
        new_color = (0, 255, 0)
        custom_alpha = 200
        self.widget.set_background_color(new_color, alpha=custom_alpha)
        self.assertEqual(self.widget.bg_color, new_color)
        self.assertEqual(self.widget.background_alpha, custom_alpha)
        self.assertIsNotNone(self.widget.bg_surface)

    def test_set_background_color_recreates_background(self):
        # Get initial background surface
        initial_bg = self.widget.bg_surface

        # Change background color
        self.widget.set_background_color((100, 100, 100), alpha=255)

        # Background surface should be recreated (different object)
        self.assertIsNotNone(self.widget.bg_surface)
        self.assertEqual(self.widget.bg_color, (100, 100, 100))
        self.assertEqual(self.widget.background_alpha, 255)


if __name__ == "__main__":
    unittest.main()
