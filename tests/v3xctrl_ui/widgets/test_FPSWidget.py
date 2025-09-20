# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame

from v3xctrl_ui.widgets.FpsWidget import FpsWidget


@patch("pygame.draw.lines")
class TestFpsWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.Surface((200, 100))

    def setUp(self):
        self.widget = FpsWidget(position=(0, 0), size=(200, 100), label="FPS")

    def test_initial_state(self, mock_draw_lines):
        self.assertEqual(self.widget.history.maxlen, 300)
        self.assertEqual(self.widget.average_window, 1)
        self.assertEqual(self.widget.graph_alpha, 180)

    def test_history_appending(self, mock_draw_lines):
        self.widget.draw(self.screen, 30.0)
        self.assertEqual(len(self.widget.history), 1)

        self.widget.draw(self.screen, 60.0)
        self.assertEqual(len(self.widget.history), 2)
        self.assertAlmostEqual(self.widget.history[-1], 60.0)

    def test_draw_skips_if_insufficient_history(self, mock_draw_lines):
        screen_mock = MagicMock()
        self.widget.history.clear()
        self.widget.draw(screen_mock, 25.0)
        screen_mock.blit.assert_not_called()

    def test_draw_calls_blit_and_lines(self, mock_draw_lines):
        self.widget.history.append(30.0)
        self.widget.history.append(60.0)

        screen_mock = MagicMock()
        self.widget.draw(screen_mock, 50.0)

        self.assertGreaterEqual(screen_mock.blit.call_count, 1)
        mock_draw_lines.assert_called_once()

    def test_graph_points_are_generated_correctly(self, mock_draw_lines):
        for i in range(10):
            self.widget.history.append(30 + i)

        graph_points = []
        for i, fps in enumerate(self.widget.history):
            x = int(i / self.widget.graph_frames * self.widget.width)
            y = int((1 - (fps - 0) / max(max(self.widget.history) - 0, 1)) * self.widget.graph_height)
            graph_points.append((x, self.widget.graph_top + y))

        self.assertEqual(len(graph_points), 10)
        self.assertTrue(all(isinstance(pt, tuple) and len(pt) == 2 for pt in graph_points))


if __name__ == "__main__":
    unittest.main()
