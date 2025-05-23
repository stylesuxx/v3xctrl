import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
import pygame.freetype
from pygame.event import Event
from pygame.locals import KEYDOWN, K_BACKSPACE, K_LEFT, K_RIGHT, K_RETURN, MOUSEBUTTONDOWN

from v3xctrl_ui.menu.input import TextInput


class TestTextInput(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.font = pygame.freetype.SysFont("Courier", 20)
        self.text_input = TextInput(
            label="Test",
            label_width=100,
            input_width=100,
            font=self.font,
            mono_font=self.font,
            on_change=lambda v: setattr(self, "changed_to", v)
        )
        self.text_input.set_position(0, 0)
        self.text_input.focused = True
        self.changed_to = None

    def tearDown(self):
        pygame.quit()

    def test_initial_state(self):
        self.assertEqual(self.text_input.get_value(), "")
        self.assertEqual(self.text_input.cursor_pos, 0)

    def test_text_input(self):
        self.text_input.handle_event(Event(KEYDOWN, {"unicode": "a", "key": 0}))
        self.assertEqual(self.text_input.get_value(), "a")
        self.assertEqual(self.text_input.cursor_pos, 1)
        self.assertEqual(self.changed_to, "a")

    def test_backspace_and_cursor(self):
        self.text_input.value = "abc"
        self.text_input.cursor_pos = 2
        self.text_input.handle_event(Event(KEYDOWN, {"key": K_BACKSPACE}))
        self.assertEqual(self.text_input.value, "ac")
        self.assertEqual(self.text_input.cursor_pos, 1)

    def test_cursor_movement(self):
        self.text_input.value = "test"
        self.text_input.cursor_pos = 2
        self.text_input.handle_event(Event(KEYDOWN, {"key": K_LEFT}))
        self.assertEqual(self.text_input.cursor_pos, 1)
        self.text_input.handle_event(Event(KEYDOWN, {"key": K_RIGHT}))
        self.assertEqual(self.text_input.cursor_pos, 2)

    def test_submit_on_return(self):
        self.text_input.value = "done"
        self.text_input.cursor_pos = 4
        self.text_input.handle_event(Event(KEYDOWN, {"key": K_RETURN}))
        self.assertEqual(self.changed_to, "done")

    def test_max_length_enforcement(self):
        self.text_input.max_length = 3
        self.text_input.value = "abc"
        self.text_input.cursor_pos = 3
        self.text_input.handle_event(Event(KEYDOWN, {"unicode": "d", "key": 0}))
        self.assertEqual(self.text_input.value, "abc")  # unchanged

    def test_mouse_focus_inside(self):
        pos = (self.text_input.input_rect.centerx, self.text_input.input_rect.centery)
        self.text_input.handle_event(Event(MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
        self.assertTrue(self.text_input.focused)

    def test_mouse_focus_outside(self):
        pos = (999, 999)
        self.text_input.handle_event(Event(MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
        self.assertFalse(self.text_input.focused)

    def test_cursor_position_on_click(self):
        self.text_input.value = "hello"
        self.text_input.cursor_pos = 0
        x = self.text_input.input_rect.right - self.text_input.input_padding - self.font.get_rect("he").width
        pos = (x, self.text_input.input_rect.centery)
        self.text_input.handle_event(Event(MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
        self.assertGreaterEqual(self.text_input.cursor_pos, 2)

    def test_cursor_blink_toggle(self):
        # Force cursor timer to be in the past so toggle triggers
        self.text_input.cursor_timer = pygame.time.get_ticks() - TextInput.CURSOR_INTERVAL - 1
        old_visibility = self.text_input.cursor_visible
        self.text_input._update_cursor_blink()
        # Cursor visibility should have toggled
        self.assertNotEqual(self.text_input.cursor_visible, old_visibility)

    def test_handle_mouse_cursor_position(self):
        # Set a longer value so the for-loop in _handle_mouse triggers
        self.text_input.value = "abcdefghij"
        self.text_input.set_position(0, 0)

        # Calculate a mouse position that lands somewhere inside the input text area
        text_x = self.text_input._get_text_x()
        # Choose rel_x between widths of value[:3] and value[:4]
        width_3 = self.text_input.mono_font.get_rect(self.text_input.value[:3]).width
        width_4 = self.text_input.mono_font.get_rect(self.text_input.value[:4]).width
        pos_x = text_x + 10 + (width_3 + width_4) // 2  # middle between 3rd and 4th char
        pos_y = self.text_input.input_rect.centery

        # Call _handle_mouse via handle_event
        self.text_input.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (pos_x, pos_y), "button": 1}))

        # Cursor pos should be set to some value <= len(value)
        self.assertTrue(0 <= self.text_input.cursor_pos <= len(self.text_input.value))

    def test_get_text_x_returns_int(self):
        self.text_input.value = "testing"
        x = self.text_input._get_text_x()
        self.assertIsInstance(x, int)

    def test_get_size(self):
        width, height = self.text_input.get_size()
        expected_width = self.text_input.label_width + self.text_input.input_padding + self.text_input.input_width
        expected_height = self.text_input.input_rect.height
        self.assertEqual(width, expected_width)
        self.assertEqual(height, expected_height)

    def test_draw_unfocused(self):
        surface = pygame.Surface((200, 50))
        self.text_input.focused = False
        self.text_input.draw(surface)  # Should draw label, input box, text, no cursor

    def test_draw_focused_cursor_visible(self):
        surface = pygame.Surface((200, 50))
        self.text_input.focused = True
        self.text_input.cursor_visible = True
        self.text_input.value = "test"
        self.text_input.cursor_pos = 2
        self.text_input.draw(surface)  # Should draw cursor

    def test_draw_focused_cursor_invisible(self):
        surface = pygame.Surface((200, 50))
        self.text_input.focused = True
        self.text_input.cursor_visible = False
        self.text_input.draw(surface)  # Should skip drawing cursor


if __name__ == "__main__":
    unittest.main()
