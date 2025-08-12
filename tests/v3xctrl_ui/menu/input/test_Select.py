import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
from pygame.freetype import SysFont
from pygame.event import Event
from pygame.locals import MOUSEBUTTONDOWN, MOUSEMOTION

from v3xctrl_ui.menu.input import Select


class TestSelect(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.font = SysFont("Arial", 20)
        self.selected_index = None

        def callback(i):
            self.selected_index = i

        self.select = Select(
            label="Quality",
            label_width=100,
            length=200,
            font=self.font,
            callback=callback
        )
        self.select.set_position(10, 10)
        self.select.set_options(["Low", "Medium", "High"], selected_index=1)

    def tearDown(self):
        pygame.quit()

    def test_initial_selection(self):
        self.assertEqual(self.select.selected_index, 1)

    def test_get_size(self):
        w, h = self.select.get_size()
        self.assertEqual(w, self.select.label_width + self.select.LABEL_PADDING + self.select.length)
        self.assertEqual(h, self.select.rect.height)

    def test_click_to_expand_and_select(self):
        # Expand dropdown
        click_expand = Event(MOUSEBUTTONDOWN, {"pos": self.select.rect.center, "button": 1})
        self.select.handle_event(click_expand)
        self.assertTrue(self.select.expanded)

        # Select first option
        click_low = Event(MOUSEBUTTONDOWN, {"pos": self.select.option_rects[0].center, "button": 1})
        self.select.handle_event(click_low)
        self.assertEqual(self.select.selected_index, 0)
        self.assertEqual(self.selected_index, 0)
        self.assertFalse(self.select.expanded)

    def test_click_outside_closes_dropdown(self):
        self.select.expanded = True
        click_outside = Event(MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 1})
        self.select.handle_event(click_outside)
        self.assertFalse(self.select.expanded)

    def test_hover_tracking(self):
        self.select.expanded = True
        motion_event = Event(MOUSEMOTION, {"pos": self.select.option_rects[2].center})
        self.select.handle_event(motion_event)
        self.assertEqual(self.select.hover_index, 2)

    def test_hover_resets_when_outside(self):
        self.select.expanded = True
        motion_event = Event(MOUSEMOTION, {"pos": (0, 0)})
        self.select.handle_event(motion_event)
        self.assertEqual(self.select.hover_index, -1)

    def test_out_of_bounds_selection(self):
        self.select.set_options(["Low", "Medium"], selected_index=5)
        self.assertEqual(self.select.selected_index, 0)

    def test_truncation_behavior(self):
        long_option = "This is a very long option that should be truncated"
        self.select.set_options([long_option])
        surface = self.select.option_surfaces[0]
        # Check surface width is less than rect width (meaning truncation likely)
        self.assertLess(surface.get_width(), self.select.rect.width)

    def test_disable_prevents_expansion_and_selection(self):
        self.select.disable()
        click_expand = Event(MOUSEBUTTONDOWN, {"pos": self.select.rect.center, "button": 1})
        self.select.handle_event(click_expand)
        self.assertFalse(self.select.expanded)

        self.select.expanded = True
        click_select = Event(MOUSEBUTTONDOWN, {"pos": self.select.option_rects[1].center, "button": 1})
        self.select.handle_event(click_select)
        # Selection callback should NOT fire; selected_index remains unchanged
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

    def test_draw_collapsed_and_expanded(self):
        surface = pygame.Surface((300, 200))
        self.select.expanded = False
        try:
            self.select.draw(surface)  # collapsed draw
        except Exception as e:
            self.fail(f"Draw failed when collapsed: {e}")

        self.select.expanded = True
        self.select.hover_index = 1
        try:
            self.select.draw(surface)  # expanded draw
        except Exception as e:
            self.fail(f"Draw failed when expanded: {e}")

    def test_no_options_draw_and_handle(self):
        self.select.set_options([])
        surface = pygame.Surface((300, 200))
        try:
            self.select.draw(surface)
        except Exception as e:
            self.fail(f"Draw failed with no options: {e}")

        # Should not crash or change state
        self.select.expanded = True
        event = Event(MOUSEBUTTONDOWN, {"pos": self.select.rect.center, "button": 1})
        self.select.handle_event(event)
        self.assertTrue(self.select.expanded)  # expanded state unchanged because no options


if __name__ == "__main__":
    unittest.main()
