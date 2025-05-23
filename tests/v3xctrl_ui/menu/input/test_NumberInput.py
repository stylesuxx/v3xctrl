import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
import pygame.freetype
from pygame.event import Event
from pygame.locals import K_BACKSPACE, K_LEFT, K_RIGHT, K_UP, K_DOWN, KEYDOWN, MOUSEBUTTONDOWN

from v3xctrl_ui.menu.input import NumberInput


class TestNumberInput(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))  # Needed for freetype init
        self.font = pygame.freetype.SysFont("Courier", 20)
        self.input = NumberInput(
            label="Test",
            label_width=100,
            input_width=100,
            min_val=1,
            max_val=99999,
            font=self.font,
            mono_font=self.font,
            on_change=lambda v: setattr(self, "changed_to", v)
        )
        self.input.set_position(0, 0)
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

    def test_out_of_range_rejection(self):
        self.input.min_val = 1
        self.input.max_val = 3
        self.input.value = "3"
        self.input.cursor_pos = 1
        self.input.handle_event(Event(KEYDOWN, {"unicode": "9", "key": 0}))
        self.assertEqual(self.input.value, "3")  # Rejected

    def test_get_value_fallback(self):
        self.input.value = "notanumber"
        self.assertEqual(self.input.get_value(), 1)  # Fallback to min_val

    def test_cursor_blink_toggle(self):
        self.input.cursor_timer = pygame.time.get_ticks() - self.input.CURSOR_INTERVAL - 1
        old_visible = self.input.cursor_visible
        self.input._update_cursor_blink()
        self.assertNotEqual(old_visible, self.input.cursor_visible)

    def test_handle_mouse_cursor_position(self):
        self.input.value = "12345"
        self.input.set_position(0, 0)
        text_x = self.input._get_text_x()
        # Position near middle of third character:
        width_2 = self.input.mono_font.get_rect(self.input.value[:2]).width
        width_3 = self.input.mono_font.get_rect(self.input.value[:3]).width
        pos_x = text_x + 10 + (width_2 + width_3) // 2
        pos_y = self.input.input_rect.centery

        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (pos_x, pos_y), "button": 1})
        self.input.handle_event(event)

        self.assertTrue(0 <= self.input.cursor_pos <= len(self.input.value))

    def test_reject_invalid_digit_input(self):
        self.input.min_val = 1
        self.input.max_val = 99
        self.input.value = "99"
        self.input.cursor_pos = 2

        # Try to insert digit '9' which would exceed max_val (999)
        event = pygame.event.Event(pygame.KEYDOWN, {"unicode": "9", "key": 0})
        self.input.handle_event(event)
        self.assertEqual(self.input.value, "99")  # unchanged

        # Try to insert non-digit character (should be ignored)
        event = pygame.event.Event(pygame.KEYDOWN, {"unicode": "a", "key": 0})
        self.input.handle_event(event)
        self.assertEqual(self.input.value, "99")  # unchanged

    def test_draw_states(self):
        surface = pygame.Surface((200, 50))

        self.input.focused = False
        self.input.draw(surface)  # No cursor drawn

        self.input.focused = True
        self.input.cursor_visible = True
        self.input.value = "123"
        self.input.cursor_pos = 1
        self.input.draw(surface)  # Cursor drawn

        self.input.cursor_visible = False
        self.input.draw(surface)  # No cursor drawn

    def test_get_size(self):
        width, height = self.input.get_size()
        expected_width = self.input.label_width + self.input.input_padding + self.input.input_width
        expected_height = self.input.input_rect.height
        self.assertEqual(width, expected_width)
        self.assertEqual(height, expected_height)

    def test_mouse_click_focus_inside(self):
        pos = (self.input.input_rect.centerx, self.input.input_rect.centery)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1})
        self.input.handle_event(event)
        self.assertTrue(self.input.focused)
        self.assertTrue(0 <= self.input.cursor_pos <= len(self.input.value))

    def test_mouse_click_focus_outside(self):
        pos = (9999, 9999)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1})
        self.input.handle_event(event)
        self.assertFalse(self.input.focused)

    def test_cursor_navigation_and_backspace(self):
        self.input.handle_event(Event(KEYDOWN, {"unicode": "4", "key": pygame.K_4}))
        self.input.handle_event(Event(KEYDOWN, {"unicode": "2", "key": pygame.K_2}))
        self.assertEqual(self.input.value, "42")

        self.input.handle_event(Event(KEYDOWN, {"key": K_LEFT, "unicode": ''}))
        self.assertEqual(self.input.cursor_pos, 1)

        self.input.handle_event(Event(KEYDOWN, {"key": K_BACKSPACE, "unicode": ''}))
        self.assertEqual(self.input.value, "2")
        self.assertEqual(self.input.cursor_pos, 0)

    def test_arrow_key_increment_decrement(self):
        self.input.value = "3"
        self.input.cursor_pos = 1
        self.input.handle_event(Event(KEYDOWN, {"key": K_UP, "unicode": ''}))
        self.assertEqual(self.input.get_value(), 4)
        self.assertEqual(self.changed_to, "4")

        self.input.handle_event(Event(KEYDOWN, {"key": K_DOWN, "unicode": ''}))
        self.assertEqual(self.input.get_value(), 3)

    def test_cursor_does_not_exceed_bounds(self):
        self.input.value = "123"
        self.input.cursor_pos = 3
        self.input.handle_event(Event(KEYDOWN, {"key": K_RIGHT, "unicode": ''}))
        self.assertEqual(self.input.cursor_pos, 3)

        self.input.handle_event(Event(KEYDOWN, {"key": K_LEFT, "unicode": ''}))
        self.assertEqual(self.input.cursor_pos, 2)

    def test_arrow_key_increment_and_decrement(self):
        self.input.value = "5"
        self.input.cursor_pos = 1

        self.input.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_UP, "unicode": ''}))
        self.assertEqual(self.input.value, "6")
        self.assertEqual(self.input.cursor_pos, len(self.input.value))

        self.input.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_DOWN, "unicode": ''}))
        self.assertEqual(self.input.value, "5")
        self.assertEqual(self.input.cursor_pos, len(self.input.value))


if __name__ == "__main__":
    unittest.main()
