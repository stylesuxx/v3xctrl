import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
from pygame.freetype import SysFont
from pygame.event import Event
from pygame.locals import MOUSEBUTTONDOWN, MOUSEMOTION

from ui.menu.Select import Select


class TestSelect(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.font = SysFont("Arial", 20)
        self.select = Select(
            label="Quality",
            label_width=100,
            width=200,
            font=self.font,
            callback=lambda i: setattr(self, "selected_index", i)
        )
        self.select.set_position(10, 10)
        self.select.set_options(["Low", "Medium", "High"], selected_index=1)
        self.selected_index = None

    def tearDown(self):
        pygame.quit()

    def test_initial_selection(self):
        self.assertEqual(self.select.selected_index, 1)

    def test_click_to_expand_and_select(self):
        click_expand = Event(MOUSEBUTTONDOWN, {"pos": self.select.rect.center, "button": 1})
        self.select.handle_event(click_expand)
        self.assertTrue(self.select.expanded)

        click_low = Event(MOUSEBUTTONDOWN, {"pos": self.select.option_rects[0].center, "button": 1})
        self.select.handle_event(click_low)
        self.assertEqual(self.select.selected_index, 0)
        self.assertEqual(self.selected_index, 0)
        self.assertFalse(self.select.expanded)

    def test_hover_tracking(self):
        self.select.expanded = True
        motion_event = Event(MOUSEMOTION, {"pos": self.select.option_rects[2].center})
        self.select.handle_event(motion_event)
        self.assertEqual(self.select.hover_index, 2)

    def test_out_of_bounds_selection(self):
        self.select.set_options(["Low", "Medium"], selected_index=5)
        self.assertEqual(self.select.selected_index, 0)

    def test_truncation_behavior(self):
        long_option = "This is a very long option that should be truncated"
        self.select.set_options([long_option])
        surface = self.select.option_surfaces[0]
        self.assertLess(surface.get_width(), self.select.rect.width)

    def test_disable_prevents_expansion(self):
        self.select.disable()
        click_expand = Event(MOUSEBUTTONDOWN, {"pos": self.select.rect.center, "button": 1})
        self.select.handle_event(click_expand)
        self.assertFalse(self.select.expanded)

    def test_disable_prevents_selection(self):
        self.select.expanded = True
        self.select.disable()
        click_select = Event(MOUSEBUTTONDOWN, {"pos": self.select.option_rects[1].center, "button": 1})
        self.select.handle_event(click_select)
        # Should not change
        self.assertIsNone(self.selected_index)

    def test_enable_restores_interaction(self):
        self.select.disable()
        self.select.enable()
        click_expand = Event(MOUSEBUTTONDOWN, {"pos": self.select.rect.center, "button": 1})
        self.select.handle_event(click_expand)
        self.assertTrue(self.select.expanded)

    def test_label_alignment_after_disable_enable(self):
        orig_y = self.select.label_rect.y
        self.select.disable()
        self.select.enable()
        self.assertEqual(self.select.label_rect.y, orig_y)


if __name__ == "__main__":
    unittest.main()
