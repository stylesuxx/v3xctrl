import pygame
from unittest.mock import patch

from ui.widgets.HorizontalIndicatorWidget import HorizontalIndicatorWidget


def test_symmetric_center_value_draws_bar_centered():
    pygame.init()
    screen = pygame.Surface((100, 100))
    widget = HorizontalIndicatorWidget(pos=(10, 10), size=(80, 20))
    widget.range_mode = "symmetric"

    with patch("pygame.draw.rect") as mock_draw:
        widget.draw(screen, value=0.0)

        # Centered x = center - bar_width/2
        expected_x = 10 + 80 // 2 - widget.bar_width // 2
        expected_y = 10 + (20 - widget.bar_height) // 2
        expected_rect = (expected_x, expected_y, widget.bar_width, widget.bar_height)

        mock_draw.assert_called_once_with(screen, pygame.Color("white"), expected_rect)


def test_value_clamped_above_one():
    pygame.init()
    screen = pygame.Surface((100, 100))
    widget = HorizontalIndicatorWidget(pos=(0, 0), size=(100, 20))
    widget.range_mode = "symmetric"

    with patch("pygame.draw.rect") as mock_draw:
        widget.draw(screen, value=5.0)  # Should be clamped to 1.0

        args = mock_draw.call_args[0]
        rect = args[2]
        x, _, _, _ = rect

        assert x > 50  # Should be on the right half of widget


def test_asymmetric_mode_draws_from_left():
    pygame.init()
    screen = pygame.Surface((100, 100))
    widget = HorizontalIndicatorWidget(pos=(0, 0), size=(100, 20))
    widget.range_mode = "asymmetric"
    widget.padding = 5

    with patch("pygame.draw.rect") as mock_draw:
        widget.draw(screen, value=0.0)

        # X should be at padding
        expected_x = widget.pos[0] + widget.padding
        rect_x = mock_draw.call_args[0][2][0]

        assert rect_x == expected_x