import unittest
from unittest.mock import MagicMock, patch
import pygame

from ui.widgets import VerticalIndicatorWidget


class TestVerticalIndicatorWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.Surface((50, 200))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.widget_size = (50, 200)
        self.widget_pos = (0, 0)

    def test_init_valid_modes(self):
        VerticalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="symmetric")
        VerticalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="positive")

    def test_init_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            VerticalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="invalid")

    @patch("pygame.draw.rect")
    def test_draw_symmetric_zero(self, mock_draw_rect):
        widget = VerticalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="symmetric")
        screen = MagicMock()

        widget.draw(screen, value=0.0)

        mock_draw_rect.assert_not_called()  # zero value results in bar_height 0

    @patch("pygame.draw.rect")
    def test_draw_symmetric_negative_and_positive(self, mock_draw_rect):
        widget = VerticalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="symmetric")
        screen = MagicMock()

        widget.draw(screen, value=-1.0)
        neg_y = mock_draw_rect.call_args_list[0][0][2].y

        mock_draw_rect.reset_mock()
        widget.draw(screen, value=1.0)
        pos_y = mock_draw_rect.call_args_list[0][0][2].y

        self.assertGreater(neg_y, pos_y)  # positive draws higher than negative

    @patch("pygame.draw.rect")
    def test_draw_positive_bottom_and_top(self, mock_draw_rect):
        widget = VerticalIndicatorWidget(self.widget_pos, self.widget_size, range_mode="positive")
        screen = MagicMock()

        widget.draw(screen, value=0.0)
        mock_draw_rect.assert_not_called()  # zero height

        widget.draw(screen, value=1.0)
        top_y = mock_draw_rect.call_args_list[0][0][2].y

        # Ensure the rect starts from the top (low y) of the widget
        self.assertLess(top_y, self.widget_size[1])

    @patch("pygame.draw.rect")
    def test_color_function_usage(self, mock_draw_rect):
        color_fn = lambda v: (255, 0, 0) if v < 0 else (0, 255, 0)
        widget = VerticalIndicatorWidget(
            self.widget_pos, self.widget_size,
            range_mode="symmetric", color_fn=color_fn
        )
        screen = MagicMock()

        widget.draw(screen, value=-0.5)
        fill_color = mock_draw_rect.call_args_list[0][0][1]
        self.assertEqual(fill_color, (255, 0, 0))

        mock_draw_rect.reset_mock()
        widget.draw(screen, value=0.5)
        fill_color = mock_draw_rect.call_args_list[0][0][1]
        self.assertEqual(fill_color, (0, 255, 0))


if __name__ == "__main__":
    unittest.main()
