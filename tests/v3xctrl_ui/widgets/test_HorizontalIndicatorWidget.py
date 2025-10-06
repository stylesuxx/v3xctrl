# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame

from v3xctrl_ui.widgets import HorizontalIndicatorWidget


@patch("pygame.draw.rect")
class TestHorizontalIndicatorWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.Surface((200, 50))

    def setUp(self):
        self.widget_size = (200, 50)
        self.widget_pos = (0, 0)

    def test_init_valid_modes(self, mock_draw_rect):
        HorizontalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="symmetric")
        HorizontalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="positive")

    def test_init_invalid_mode_raises(self, mock_draw_rect):
        with self.assertRaises(ValueError):
            HorizontalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="invalid")

    def test_draw_positive_zero_and_one(self, mock_draw_rect):
        widget = HorizontalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="positive")
        screen = MagicMock()

        widget.draw(screen, value=0.0)
        zero_x = mock_draw_rect.call_args_list[0][0][2].x

        mock_draw_rect.reset_mock()
        widget.draw(screen, value=1.0)
        one_x = mock_draw_rect.call_args_list[0][0][2].x

        self.assertLess(zero_x, one_x)

    def test_color_function_usage(self, mock_draw_rect):
        color_fn = lambda v: (255, 0, 0) if v < 0 else (0, 255, 0)
        widget = HorizontalIndicatorWidget(
            self.widget_pos, self.widget_size,
            range_mode="symmetric", color_fn=color_fn
        )

        screen = MagicMock()
        widget.draw(screen, value=-0.5)

        self.assertEqual(mock_draw_rect.call_args_list[0][0][1], (255, 0, 0))

        mock_draw_rect.reset_mock()
        widget.draw(screen, value=0.5)
        self.assertEqual(mock_draw_rect.call_args_list[0][0][1], (0, 255, 0))


if __name__ == "__main__":
    unittest.main()
