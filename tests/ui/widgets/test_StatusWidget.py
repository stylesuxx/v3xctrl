import unittest
import pygame

from ui.colors import YELLOW, GREEN, RED, GREY
from ui.widgets.StatusWidget import StatusWidget


class TestStatusWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.widget = StatusWidget(position=(0, 0), size=20, label="TEST")
        self.screen = pygame.Surface((200, 100))

    def test_initial_color_is_default(self):
        # Initial value before any draw
        self.assertEqual(self.widget.color, GREY)

    def test_draw_sets_status_color_waiting(self):
        self.widget.draw(self.screen, "waiting")
        self.assertEqual(self.widget.color, YELLOW)

    def test_draw_sets_status_color_success(self):
        self.widget.draw(self.screen, "success")
        self.assertEqual(self.widget.color, GREEN)

    def test_draw_sets_status_color_fail(self):
        self.widget.draw(self.screen, "fail")
        self.assertEqual(self.widget.color, RED)

    def test_draw_sets_status_color_unknown_defaults(self):
        self.widget.draw(self.screen, "foobar")
        self.assertEqual(self.widget.color, GREY)

    def test_draw_executes_without_crash(self):
        try:
            self.widget.draw(self.screen, "success")
        except Exception as e:
            self.fail(f"draw() raised exception unexpectedly: {e}")

    def test_draw_extra_is_called(self):
        class ExtendedStatusWidget(StatusWidget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.extra_called = False

            def draw_extra(self, surface):
                self.extra_called = True

        widget = ExtendedStatusWidget((0, 0), 20, "Label")
        screen = pygame.Surface((100, 50))
        widget.draw(screen, "success")
        self.assertTrue(widget.extra_called)


if __name__ == "__main__":
    unittest.main()
