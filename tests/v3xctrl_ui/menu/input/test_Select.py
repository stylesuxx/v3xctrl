import os
import unittest

import pygame
from pygame.freetype import SysFont
from pygame.event import Event
from pygame.locals import MOUSEBUTTONDOWN, MOUSEMOTION

from v3xctrl_ui.menu.input import Select

os.environ["SDL_VIDEODRIVER"] = "dummy"


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
        self.assertEqual(self.select.get_size(), (
            self.select.label_width + self.select.LABEL_PADDING + self.select.length,
            self.select.rect.height
        ))

    def test_click_to_expand_and_select(self):
        click_expand = Event(MOUSEBUTTONDOWN, {
            "pos": self.select.rect.center,
            "button": 1
        })
        self.select.handle_event(click_expand)
        self.assertTrue(self.select.expanded)

        click_low = Event(MOUSEBUTTONDOWN, {
            "pos": self.select.option_rects[0].center,
            "button": 1
        })
        self.select.handle_event(click_low)
        self.assertEqual(self.select.selected_index, 0)
        self.assertEqual(self.selected_index, 0)
        self.assertFalse(self.select.expanded)

    def test_click_outside_closes_dropdown(self):
        self.select.expanded = True
        click_outside = Event(MOUSEBUTTONDOWN, {
            "pos": (0, 0),
            "button": 1
        })
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
        self.assertLess(surface.get_width(), self.select.rect.width)

    def test_disable_prevents_expansion_and_selection(self):
        self.select.disable()
        click_expand = Event(MOUSEBUTTONDOWN, {
            "pos": self.select.rect.center,
            "button": 1
        })
        self.select.handle_event(click_expand)
        self.assertFalse(self.select.expanded)

        self.select.expanded = True
        click_select = Event(MOUSEBUTTONDOWN, {
            "pos": self.select.option_rects[1].center,
            "button": 1
        })
        self.select.handle_event(click_select)
        self.assertIsNone(self.selected_index)

    def test_enable_restores_interaction(self):
        self.select.disable()
        self.select.enable()
        click_expand = Event(MOUSEBUTTONDOWN, {
            "pos": self.select.rect.center,
            "button": 1
        })
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
            self.select.draw(surface)
        except Exception as e:
            self.fail(f"Draw failed when collapsed: {e}")

        self.select.expanded = True
        self.select.hover_index = 1
        try:
            self.select.draw(surface)
        except Exception as e:
            self.fail(f"Draw failed when expanded: {e}")

    def test_no_options_draw_and_handle(self):
        self.select.set_options([])
        surface = pygame.Surface((300, 200))
        try:
            self.select.draw(surface)
        except Exception as e:
            self.fail(f"Draw failed with no options: {e}")

        self.select.expanded = True
        event = Event(MOUSEBUTTONDOWN, {
            "pos": self.select.rect.center,
            "button": 1
        })
        self.select.handle_event(event)
        self.assertTrue(self.select.expanded)

    def test_handle_event_with_empty_options(self):
        self.select.set_options([])

        click_event = Event(MOUSEBUTTONDOWN, {
            "pos": self.select.rect.center,
            "button": 1
        })
        self.assertFalse(self.select.handle_event(click_event))

        motion_event = Event(MOUSEMOTION, {"pos": self.select.rect.center})
        self.assertFalse(self.select.handle_event(motion_event))

    def test_handle_event_when_disabled(self):
        self.select.disable()

        click_event = Event(MOUSEBUTTONDOWN, {
            "pos": self.select.rect.center,
            "button": 1
        })
        self.assertFalse(self.select.handle_event(click_event))

        motion_event = Event(MOUSEMOTION, {"pos": self.select.rect.center})
        self.assertFalse(self.select.handle_event(motion_event))

    def test_handle_event_non_left_click(self):
        right_click = Event(MOUSEBUTTONDOWN, {"pos": self.select.rect.center, "button": 3})
        self.assertFalse(self.select.handle_event(right_click))
        self.assertFalse(self.select.expanded)

        middle_click = Event(MOUSEBUTTONDOWN, {"pos": self.select.rect.center, "button": 2})
        self.assertFalse(self.select.handle_event(middle_click))
        self.assertFalse(self.select.expanded)

    def test_handle_event_unknown_event_type(self):
        key_event = Event(pygame.KEYDOWN, {"key": pygame.K_SPACE})
        self.assertFalse(self.select.handle_event(key_event))

    def test_click_outside_when_not_expanded(self):
        self.select.expanded = False
        click_outside = Event(MOUSEBUTTONDOWN, {"pos": (0, 0), "button": 1})
        self.assertFalse(self.select.handle_event(click_outside))
        self.assertFalse(self.select.expanded)

    def test_motion_when_not_expanded(self):
        self.select.expanded = False
        motion_event = Event(MOUSEMOTION, {"pos": self.select.rect.center})
        self.assertFalse(self.select.handle_event(motion_event))

    def test_set_options_with_negative_index(self):
        self.select.set_options(["Option1", "Option2"], selected_index=-1)
        self.assertEqual(self.select.selected_index, 0)

    def test_set_options_empty_list_with_index(self):
        self.select.set_options([], selected_index=5)
        self.assertEqual(self.select.selected_index, 0)

    def test_render_label_and_caret_without_position_set(self):
        new_select = Select(
            label="Test",
            label_width=100,
            length=200,
            font=self.font,
            callback=lambda x: None
        )

        new_select._render_label_and_caret()
        self.assertIsNotNone(new_select.label_surface)

    def test_text_truncation_edge_cases(self):
        short_select = Select(
            label="Test",
            label_width=50,
            length=50,
            font=self.font,
            callback=lambda x: None
        )
        short_select.set_position(0, 0)

        long_options = ["This is an extremely long option name that will definitely be truncated"]
        short_select.set_options(long_options)

        rendered_text = short_select.option_surfaces[0]
        self.assertIsNotNone(rendered_text)

    def test_text_truncation_single_character(self):
        tiny_select = Select(
            label="T",
            label_width=10,
            length=20,
            font=self.font,
            callback=lambda x: None
        )
        tiny_select.set_position(0, 0)

        options = ["VeryLongOption"]
        tiny_select.set_options(options)

        self.assertEqual(len(tiny_select.option_surfaces), 1)

    def test_update_option_rects_with_empty_options(self):
        self.select.set_options([])
        self.assertEqual(len(self.select.option_rects), 0)
        self.assertIsNotNone(self.select.full_expanded_rect)

    def test_draw_with_disabled_and_expanded(self):
        surface = pygame.Surface((300, 200))
        self.select.disable()
        self.select.expanded = True

        try:
            self.select.draw(surface)
        except Exception as e:
            self.fail(f"Draw failed when disabled but expanded: {e}")

    def test_draw_with_no_full_expanded_rect(self):
        surface = pygame.Surface((300, 200))
        self.select.expanded = True
        self.select.full_expanded_rect = None

        try:
            self.select.draw(surface)
        except Exception as e:
            self.fail(f"Draw failed with None full_expanded_rect: {e}")

    def test_select_option_when_expanded_false(self):
        self.select.expanded = False

        click_option = Event(MOUSEBUTTONDOWN, {
            "pos": (self.select.rect.x + 50, self.select.rect.y + 50),
            "button": 1
        })

        original_index = self.select.selected_index
        self.select.handle_event(click_option)

        self.assertEqual(self.select.selected_index, original_index)

    def test_toggle_expansion_multiple_times(self):
        self.assertFalse(self.select.expanded)

        click_event = Event(MOUSEBUTTONDOWN, {"pos": self.select.rect.center, "button": 1})

        self.assertTrue(self.select.handle_event(click_event))
        self.assertTrue(self.select.expanded)

        self.assertTrue(self.select.handle_event(click_event))
        self.assertFalse(self.select.expanded)

        self.assertTrue(self.select.handle_event(click_event))
        self.assertTrue(self.select.expanded)

    def test_hover_with_exact_option_boundaries(self):
        self.select.expanded = True

        top_edge = Event(MOUSEMOTION, {
            "pos": (self.select.option_rects[0].centerx, self.select.option_rects[0].top)
        })
        self.select.handle_event(top_edge)
        self.assertEqual(self.select.hover_index, 0)

        last_idx = len(self.select.option_rects) - 1
        bottom_edge = Event(MOUSEMOTION, {
            "pos": (self.select.option_rects[last_idx].centerx, self.select.option_rects[last_idx].bottom - 1)
        })
        self.select.handle_event(bottom_edge)
        self.assertEqual(self.select.hover_index, last_idx)


if __name__ == "__main__":
    unittest.main()
