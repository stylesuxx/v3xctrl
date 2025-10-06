# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock

import pygame

from v3xctrl_ui.colors import BLACK
from v3xctrl_ui.widgets import StatusValueWidget


class TestStatusValueWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.mock_screen = pygame.Surface((200, 100))

    def setUp(self):
        self.widget = StatusValueWidget(position=(0, 0), size=20, label="L")

    def test_inherits_from_status_widget(self):
        from v3xctrl_ui.widgets.StatusWidget import StatusWidget
        self.assertIsInstance(self.widget, StatusWidget)

    def test_default_value_is_none(self):
        self.assertIsNone(self.widget.value)

    def test_set_value_updates_value(self):
        self.widget.set_value(42)
        self.assertEqual(self.widget.value, 42)

    def test_draw_extra_renders_value_when_set(self):
        self.widget.set_value(99)

        mock_surface = MagicMock()
        mock_rendered = MagicMock()
        mock_rect = pygame.Rect(0, 0, 10, 10)

        self.widget.value_font = MagicMock()
        self.widget.value_font.render_to.return_value = (mock_rendered, mock_rect)

        self.widget.draw_extra(mock_surface)

        self.widget.value_font.render_to.assert_called_once()

    def test_draw_extra_skips_render_when_none(self):
        self.widget.set_value(None)
        mock_surface = MagicMock()

        self.widget.font = MagicMock()
        self.widget.draw_extra(mock_surface)

        self.widget.font.render.assert_not_called()
        mock_surface.blit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
