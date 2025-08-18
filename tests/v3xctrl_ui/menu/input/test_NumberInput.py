import os

import unittest
from unittest.mock import Mock, patch

import pygame
import pygame.freetype
from pygame.event import Event
from pygame.locals import (
  K_BACKSPACE,
  K_LEFT,
  K_RIGHT,
  K_UP,
  K_DOWN,
  K_RETURN,
  KEYDOWN,
  MOUSEBUTTONDOWN,
)

from v3xctrl_ui.menu.input import NumberInput, BaseInput


os.environ["SDL_VIDEODRIVER"] = "dummy"


class TestNumberInput(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.font = pygame.freetype.SysFont("Courier", 20)
        self.mock_on_change = Mock()

        self.input = NumberInput(
            label="Test",
            label_width=100,
            input_width=200,
            min_val=1,
            max_val=99999,
            font=self.font,
            mono_font=self.font,
            on_change=self.mock_on_change
        )
        self.input.set_position(0, 0)

    def tearDown(self):
        pygame.quit()

    def test_initialization(self):
        self.assertEqual(self.input.label, "Test")
        self.assertEqual(self.input.label_width, 100)
        self.assertEqual(self.input.input_width, 200)
        self.assertEqual(self.input.min_val, 1)
        self.assertEqual(self.input.max_val, 99999)
        self.assertEqual(self.input.on_change, self.mock_on_change)

        self.assertEqual(self.input.get_value(), 1)
        self.assertEqual(self.input.value, "")
        self.assertEqual(self.input.cursor_pos, 0)
        self.assertFalse(self.input.focused)

    def test_initialization_without_callback(self):
        widget = NumberInput(
            label="Test",
            label_width=50,
            input_width=100,
            min_val=0,
            max_val=100,
            font=self.font,
            mono_font=self.font
        )
        self.assertIsNone(widget.on_change)

    def test_single_digit_input_valid(self):
        self.input.focused = True
        event = Event(KEYDOWN, {"unicode": "5", "key": pygame.K_5})

        self.assertTrue(self.input.handle_event(event))
        self.assertEqual(self.input.value, "5")
        self.assertEqual(self.input.get_value(), 5)
        self.assertEqual(self.input.cursor_pos, 1)
        self.mock_on_change.assert_called_once_with("5")

    def test_multiple_digit_input_valid(self):
        self.input.focused = True
        digits = ["1", "2", "3"]

        for digit in digits:
            event = Event(KEYDOWN, {"unicode": digit, "key": ord(digit)})
            self.input.handle_event(event)

        self.assertEqual(self.input.value, "123")
        self.assertEqual(self.input.get_value(), 123)
        self.assertEqual(self.input.cursor_pos, 3)
        self.assertEqual(self.mock_on_change.call_count, 3)

    def test_digit_insertion_at_cursor(self):
        self.input.focused = True
        self.input.value = "135"
        self.input.cursor_pos = 1
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "2", "key": pygame.K_2})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "1235")
        self.assertEqual(self.input.get_value(), 1235)
        self.assertEqual(self.input.cursor_pos, 2)

    def test_input_exceeds_max_value_rejected(self):
        self.input.focused = True
        self.input.min_val = 1
        self.input.max_val = 100
        self.input.value = "99"
        self.input.cursor_pos = 2
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "9", "key": pygame.K_9})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "99")
        self.assertEqual(self.input.cursor_pos, 2)
        self.mock_on_change.assert_not_called()

    def test_input_below_min_value_rejected(self):
        self.input.focused = True
        self.input.min_val = 10
        self.input.max_val = 100
        self.input.value = ""
        self.input.cursor_pos = 0
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "5", "key": pygame.K_5})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "")
        self.mock_on_change.assert_not_called()

    def test_non_digit_input_rejected(self):
        self.input.focused = True
        non_digits = ["a", "!", " ", ".", "-", "+"]

        for char in non_digits:
            self.input.value = "5"
            self.input.cursor_pos = 1
            self.mock_on_change.reset_mock()

            event = Event(KEYDOWN, {"unicode": char, "key": ord(char)})
            self.input.handle_event(event)

            self.assertEqual(self.input.value, "5")
            self.mock_on_change.assert_not_called()

    def test_max_length_enforcement(self):
        self.input.focused = True
        self.input.min_val = 1
        self.input.max_val = 99999
        self.input.value = "12345"
        self.input.cursor_pos = 5
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "6", "key": pygame.K_6})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "12345")
        self.mock_on_change.assert_not_called()

    def test_up_arrow_increment(self):
        self.input.focused = True
        self.input.value = "5"
        self.input.cursor_pos = 1
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_UP, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "6")
        self.assertEqual(self.input.get_value(), 6)
        self.assertEqual(self.input.cursor_pos, 1)
        self.mock_on_change.assert_called_once_with("6")

    def test_down_arrow_decrement(self):
        self.input.focused = True
        self.input.value = "5"
        self.input.cursor_pos = 1
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_DOWN, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "4")
        self.assertEqual(self.input.get_value(), 4)
        self.assertEqual(self.input.cursor_pos, 1)
        self.mock_on_change.assert_called_once_with("4")

    def test_up_arrow_at_max_value(self):
        self.input.focused = True
        self.input.max_val = 10
        self.input.value = "10"
        self.input.cursor_pos = 2
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_UP, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "10")
        self.assertEqual(self.input.get_value(), 10)

    def test_down_arrow_at_min_value(self):
        self.input.focused = True
        self.input.min_val = 1
        self.input.value = "1"
        self.input.cursor_pos = 1
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_DOWN, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "1")
        self.assertEqual(self.input.get_value(), 1)

    def test_arrow_keys_with_empty_value(self):
        self.input.focused = True
        self.input.value = ""
        self.input.min_val = 5
        self.input.max_val = 15
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_UP, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.value, "")

        event = Event(KEYDOWN, {"key": K_DOWN, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.value, "")

    def test_arrow_keys_with_non_digit_value(self):
        self.input.focused = True
        self.input.value = "abc"
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_UP, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.value, "abc")
        self.mock_on_change.assert_not_called()

    def test_get_value_with_valid_number(self):
        self.input.value = "123"
        self.assertEqual(self.input.get_value(), 123)

    def test_get_value_with_empty_string(self):
        self.input.value = ""
        self.assertEqual(self.input.get_value(), self.input.min_val)

    def test_get_value_with_invalid_string(self):
        invalid_values = ["abc", "12.34", "1a2", "", "   "]
        for invalid in invalid_values:
            self.input.value = invalid
            self.assertEqual(self.input.get_value(), self.input.min_val)

    def test_backspace_handling(self):
        self.input.focused = True
        self.input.value = "123"
        self.input.cursor_pos = 2

        event = Event(KEYDOWN, {"key": K_BACKSPACE, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "13")
        self.assertEqual(self.input.cursor_pos, 1)

    def test_cursor_movement(self):
        self.input.focused = True
        self.input.value = "123"
        self.input.cursor_pos = 2

        event = Event(KEYDOWN, {"key": K_LEFT, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.cursor_pos, 1)

        event = Event(KEYDOWN, {"key": K_RIGHT, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.cursor_pos, 2)

    def test_cursor_boundaries(self):
        self.input.focused = True
        self.input.value = "123"

        self.input.cursor_pos = 0
        event = Event(KEYDOWN, {"key": K_LEFT, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.cursor_pos, 0)

        self.input.cursor_pos = 3
        event = Event(KEYDOWN, {"key": K_RIGHT, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.cursor_pos, 3)

    def test_mouse_focus_inside(self):
        self.input.focused = False
        pos = (self.input.input_rect.centerx, self.input.input_rect.centery)
        event = Event(MOUSEBUTTONDOWN, {"pos": pos, "button": 1})
        self.assertTrue(self.input.handle_event(event))
        self.assertTrue(self.input.focused)

    def test_mouse_focus_outside(self):
        self.input.focused = True
        pos = (999, 999)
        event = Event(MOUSEBUTTONDOWN, {"pos": pos, "button": 1})
        self.assertFalse(self.input.handle_event(event))
        self.assertFalse(self.input.focused)

    def test_mouse_cursor_positioning(self):
        self.input.focused = True
        self.input.value = "12345"
        self.input.cursor_pos = 0

        text_x = self.input._get_text_x()
        text_width = self.input.mono_font.get_rect("12").width
        click_x = text_x + self.input.input_padding + text_width
        click_y = self.input.input_rect.centery

        event = Event(MOUSEBUTTONDOWN, {"pos": (click_x, click_y), "button": 1})
        self.input.handle_event(event)

        self.assertTrue(0 <= self.input.cursor_pos <= len(self.input.value))

    def test_unfocused_key_events_ignored(self):
        self.input.focused = False
        self.input.value = "5"
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "7", "key": pygame.K_7})
        self.assertFalse(self.input.handle_event(event))

        self.assertEqual(self.input.value, "5")
        self.mock_on_change.assert_not_called()

    def test_unicode_attribute_missing(self):
        self.input.focused = True

        event = Event(KEYDOWN, {"key": pygame.K_5})
        if hasattr(event, 'unicode'):
            delattr(event, 'unicode')

        self.assertTrue(self.input.handle_event(event))
        self.assertEqual(self.input.value, "")

    def test_return_key_handling(self):
        self.input.focused = True
        self.input.value = "42"
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_RETURN, "unicode": ""})
        self.input.handle_event(event)

        self.mock_on_change.assert_not_called()

    def test_draw_methods_work(self):
        surface = pygame.Surface((400, 100))

        self.input.focused = False
        self.input.draw(surface)

        self.input.focused = True
        self.input.cursor_visible = True
        self.input.value = "123"
        self.input.cursor_pos = 2
        self.input.draw(surface)

        self.input.cursor_visible = False
        self.input.draw(surface)

    def test_size_calculation(self):
        expected_width = 100 + 10 + 200

        width, height = self.input.get_size()
        self.assertIsInstance(width, int)
        self.assertIsInstance(height, int)
        self.assertEqual(width, expected_width)
        self.assertGreater(height, 0)

    def test_inheritance_from_base_input(self):
        self.assertIsInstance(self.input, BaseInput)

    def test_cursor_blink_functionality(self):
        with patch('pygame.time.get_ticks') as mock_ticks:
            mock_ticks.return_value = self.input.cursor_timer + self.input.CURSOR_INTERVAL + 1

            old_visibility = self.input.cursor_visible
            self.input._update_cursor_blink()
            new_visibility = self.input.cursor_visible

            self.assertNotEqual(old_visibility, new_visibility)

    def test_multiple_inputs_independence(self):
        second_input = NumberInput(
            label="Second",
            label_width=50,
            input_width=150,
            min_val=0,
            max_val=100,
            font=self.font,
            mono_font=self.font
        )

        self.input.value = "42"
        second_input.value = "17"

        self.assertEqual(self.input.get_value(), 42)
        self.assertEqual(second_input.get_value(), 17)

    def test_edge_case_values(self):
        zero_input = NumberInput(
            label="Zero",
            label_width=50,
            input_width=100,
            min_val=0,
            max_val=10,
            font=self.font,
            mono_font=self.font
        )
        zero_input.focused = True

        event = Event(KEYDOWN, {"unicode": "0", "key": pygame.K_0})
        zero_input.handle_event(event)
        self.assertEqual(zero_input.get_value(), 0)

    def test_value_validation_on_range_change(self):
        self.input.value = "50"
        self.assertEqual(self.input.get_value(), 50)

        self.input.min_val = 60
        self.input.max_val = 80

        self.assertEqual(self.input.get_value(), 50)

    def test_position_setting(self):
        self.input.set_position(50, 100)

        self.assertEqual(self.input.x, 50)
        self.assertEqual(self.input.y, 100)

        expected_input_x = 50 + 100 + 10
        self.assertEqual(self.input.input_rect.x, expected_input_x)
        self.assertEqual(self.input.input_rect.y, 100)


if __name__ == "__main__":
    unittest.main()
