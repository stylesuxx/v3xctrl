import unittest
from unittest.mock import patch
import pygame

from v3xctrl_ui.colors import WHITE, GREY
from v3xctrl_ui.widgets import TextWidget


class TestTextWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.widget = TextWidget(position=(10, 20), length=100)
        self.screen = pygame.Surface((200, 100), pygame.SRCALPHA)

    def test_initial_values(self):
        self.assertEqual(self.widget.position, (10, 20))
        self.assertEqual(self.widget.length, 100)
        self.assertEqual(self.widget.top_padding, 4)
        self.assertEqual(self.widget.bottom_padding, 4)
        self.assertEqual(self.widget.color, WHITE)
        self.assertEqual(self.widget.bg_color, GREY)
        self.assertEqual(self.widget.background_alpha, 180)
        self.assertIsNone(self.widget.surface)

    def test_draw_sets_surface_and_text_rect(self):
        self.widget.draw(self.screen, "Test")
        self.assertIsNotNone(self.widget.surface)
        self.assertGreater(self.widget.surface.get_height(), 0)
        self.assertEqual(self.widget.surface.get_width(), self.widget.length)
        self.assertIsNotNone(self.widget.text_surface)
        self.assertTrue(self.widget.text_rect.width > 0)
        self.assertTrue(self.widget.widget_height > 0)

    def test_draw_executes_without_crash(self):
        try:
            self.widget.draw(self.screen, "Draw safely")
        except Exception as e:
            self.fail(f"draw() raised an exception unexpectedly: {e}")

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

        pixel = self.widget.surface.get_at((expected_x + 1, expected_y + 1))
        self.assertNotEqual(pixel.a, 0)


if __name__ == "__main__":
    unittest.main()
