import unittest
from unittest.mock import patch, MagicMock

import pygame

from ui.colors import YELLOW, GREEN, RED, GREY
from ui.widgets import StatusWidget


class TestStatusWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.Surface((200, 100))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.widget = StatusWidget(position=(0, 0), size=20, label="TEST")

    def test_initial_color_is_default(self):
        self.assertEqual(self.widget.color, GREY)

    def test_set_status_waiting(self):
        self.widget.set_status("waiting")
        self.assertEqual(self.widget.color, YELLOW)

    def test_set_status_success(self):
        self.widget.set_status("success")
        self.assertEqual(self.widget.color, GREEN)

    def test_set_status_fail(self):
        self.widget.set_status("fail")
        self.assertEqual(self.widget.color, RED)

    def test_set_status_unknown_defaults(self):
        self.widget.set_status("foobar")
        self.assertEqual(self.widget.color, GREY)

    @patch("pygame.draw.rect")
    def test_draw_calls_draw_rect_and_blit(self, mock_draw_rect):
        screen = MagicMock()
        self.widget.draw(screen)

        mock_draw_rect.assert_called_once_with(
            self.widget.surface, self.widget.color, self.widget.square_rect
        )
        screen.blit.assert_called_once()

    def test_draw_extra_is_called(self):
        class ExtendedStatusWidget(StatusWidget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.called = False

            def draw_extra(self, surface):
                self.called = True

        widget = ExtendedStatusWidget((0, 0), 20, "Label")
        screen = MagicMock()
        widget.draw(screen)
        self.assertTrue(widget.called)


if __name__ == "__main__":
    unittest.main()
