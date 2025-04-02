import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
import pygame.freetype
from pygame.event import Event
from pygame.locals import K_BACKSPACE, K_LEFT, K_RIGHT, K_UP, K_DOWN, KEYDOWN, MOUSEBUTTONDOWN

from src.ui.menu.NumberInput import NumberInput


class TestNumberInput(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))  # Needed for freetype init
        self.font = pygame.freetype.SysFont("Courier", 20)
        self.input = NumberInput(
            label="Test",
            x=0,
            y=0,
            label_width=100,
            input_width=100,
            min_val=1,
            max_val=99999,
            font=self.font,
            mono_font=self.font,
            on_change=lambda v: setattr(self, "changed_to", v)
        )
        self.input.focused = True
        self.changed_to = None

    def tearDown(self):
        pygame.quit()

    def test_initial_state(self):
        self.assertEqual(self.input.get_value(), 1)
        self.assertEqual(self.input.value, "")

    def test_text_input_within_range(self):
        self.input.handle_event(Event(KEYDOWN, {"unicode": "2", "key": 0}))
        self.assertEqual(self.input.value, "2")
        self.assertEqual(self.input.get_value(), 2)

    def test_cursor_navigation_and_backspace(self):
        self.input.handle_event(Event(KEYDOWN, {"unicode": "4", "key": 0}))
        self.input.handle_event(Event(KEYDOWN, {"unicode": "2", "key": 0}))
        self.assertEqual(self.input.value, "42")

        self.input.handle_event(Event(KEYDOWN, {"key": K_LEFT}))
        self.assertEqual(self.input.cursor_pos, 1)

        self.input.handle_event(Event(KEYDOWN, {"key": K_BACKSPACE}))
        self.assertEqual(self.input.value, "2")
        self.assertEqual(self.input.cursor_pos, 0)

    def test_arrow_key_increment_decrement(self):
        self.input.value = "3"
        self.input.cursor_pos = 1
        self.input.handle_event(Event(KEYDOWN, {"key": K_UP}))
        self.assertEqual(self.input.get_value(), 4)
        self.assertEqual(self.changed_to, "4")

        self.input.handle_event(Event(KEYDOWN, {"key": K_DOWN}))
        self.assertEqual(self.input.get_value(), 3)

    def test_out_of_range_rejection(self):
        self.input.min_val = 1
        self.input.max_val = 3
        self.input.value = "3"
        self.input.cursor_pos = 1
        self.input.handle_event(Event(KEYDOWN, {"unicode": "9", "key": 0}))
        self.assertEqual(self.input.value, "3")  # Rejected

    def test_cursor_does_not_exceed_bounds(self):
        self.input.value = "123"
        self.input.cursor_pos = 3
        self.input.handle_event(Event(KEYDOWN, {"key": K_RIGHT}))
        self.assertEqual(self.input.cursor_pos, 3)

        self.input.handle_event(Event(KEYDOWN, {"key": K_LEFT}))
        self.assertEqual(self.input.cursor_pos, 2)

    def test_mouse_click_focus_inside(self):
        inside_pos = (self.input.input_rect.centerx, self.input.input_rect.centery)
        event = Event(MOUSEBUTTONDOWN, {"pos": inside_pos, "button": 1})
        self.input.handle_event(event)
        self.assertTrue(self.input.focused)

    def test_mouse_click_focus_outside(self):
        outside_pos = (500, 500)
        event = Event(MOUSEBUTTONDOWN, {"pos": outside_pos, "button": 1})
        self.input.handle_event(event)
        self.assertFalse(self.input.focused)

    def test_get_value_fallback(self):
        self.input.value = "notanumber"
        self.assertEqual(self.input.get_value(), 1)  # Fallback to min_val


if __name__ == "__main__":
    unittest.main()
