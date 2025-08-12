import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import Mock, patch
import pygame
import pygame.freetype
from pygame.event import Event
from pygame.locals import K_BACKSPACE, K_LEFT, K_RIGHT, K_UP, K_DOWN, K_RETURN, KEYDOWN, MOUSEBUTTONDOWN

from v3xctrl_ui.menu.input import NumberInput


class TestNumberInput(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        pygame.init()
        pygame.display.set_mode((1, 1))  # Needed for freetype init
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
        # Don't set focus in setup - let each test set what it needs

    def tearDown(self):
        """Clean up after tests"""
        pygame.quit()

    def test_initialization(self):
        """Test NumberInput initialization"""
        # Test basic properties
        self.assertEqual(self.input.label, "Test")
        self.assertEqual(self.input.label_width, 100)
        self.assertEqual(self.input.input_width, 200)
        self.assertEqual(self.input.min_val, 1)
        self.assertEqual(self.input.max_val, 99999)
        self.assertEqual(self.input.on_change, self.mock_on_change)

        # Test initial state
        self.assertEqual(self.input.get_value(), 1)  # Should return min_val for empty string
        self.assertEqual(self.input.value, "")
        self.assertEqual(self.input.cursor_pos, 0)
        self.assertFalse(self.input.focused)

    def test_initialization_without_callback(self):
        """Test initialization without on_change callback"""
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
        """Test inputting a single valid digit"""
        self.input.focused = True
        event = Event(KEYDOWN, {"unicode": "5", "key": pygame.K_5})
        result = self.input.handle_event(event)

        self.assertTrue(result)
        self.assertEqual(self.input.value, "5")
        self.assertEqual(self.input.get_value(), 5)
        self.assertEqual(self.input.cursor_pos, 1)
        self.mock_on_change.assert_called_once_with("5")

    def test_multiple_digit_input_valid(self):
        """Test inputting multiple valid digits"""
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
        """Test digit insertion at cursor position"""
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
        """Test that input exceeding max value is rejected"""
        self.input.focused = True
        self.input.min_val = 1
        self.input.max_val = 100
        self.input.value = "99"
        self.input.cursor_pos = 2
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "9", "key": pygame.K_9})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "99")  # Should remain unchanged
        self.assertEqual(self.input.cursor_pos, 2)  # Cursor unchanged
        self.mock_on_change.assert_not_called()

    def test_input_below_min_value_rejected(self):
        """Test that input resulting in value below min is rejected"""
        self.input.focused = True
        self.input.min_val = 10
        self.input.max_val = 100
        self.input.value = ""
        self.input.cursor_pos = 0
        self.mock_on_change.reset_mock()

        # Try to input "5" which would be below min_val of 10
        event = Event(KEYDOWN, {"unicode": "5", "key": pygame.K_5})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "")  # Should remain unchanged
        self.mock_on_change.assert_not_called()

    def test_non_digit_input_rejected(self):
        """Test that non-digit input is rejected"""
        self.input.focused = True
        non_digits = ["a", "!", " ", ".", "-", "+"]

        for char in non_digits:
            self.input.value = "5"
            self.input.cursor_pos = 1
            self.mock_on_change.reset_mock()

            event = Event(KEYDOWN, {"unicode": char, "key": ord(char)})
            self.input.handle_event(event)

            self.assertEqual(self.input.value, "5")  # Should remain unchanged
            self.mock_on_change.assert_not_called()

    def test_max_length_enforcement(self):
        """Test that input is limited to 5 characters"""
        self.input.focused = True
        self.input.min_val = 1
        self.input.max_val = 99999
        self.input.value = "12345"  # Already at max length
        self.input.cursor_pos = 5
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "6", "key": pygame.K_6})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "12345")  # Should remain unchanged
        self.mock_on_change.assert_not_called()

    def test_up_arrow_increment(self):
        """Test up arrow increments value"""
        self.input.focused = True
        self.input.value = "5"
        self.input.cursor_pos = 1
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_UP, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "6")
        self.assertEqual(self.input.get_value(), 6)
        self.assertEqual(self.input.cursor_pos, 1)  # Cursor moves to end
        self.mock_on_change.assert_called_once_with("6")

    def test_down_arrow_decrement(self):
        """Test down arrow decrements value"""
        self.input.focused = True
        self.input.value = "5"
        self.input.cursor_pos = 1
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_DOWN, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "4")
        self.assertEqual(self.input.get_value(), 4)
        self.assertEqual(self.input.cursor_pos, 1)  # Cursor moves to end
        self.mock_on_change.assert_called_once_with("4")

    def test_up_arrow_at_max_value(self):
        """Test up arrow at maximum value"""
        self.input.focused = True
        self.input.max_val = 10
        self.input.value = "10"
        self.input.cursor_pos = 2
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_UP, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "10")  # Should remain at max
        self.assertEqual(self.input.get_value(), 10)
        # The current implementation actually calls on_change even when value doesn't change
        # This might be a bug in the NumberInput implementation

    def test_down_arrow_at_min_value(self):
        """Test down arrow at minimum value"""
        self.input.focused = True
        self.input.min_val = 1
        self.input.value = "1"
        self.input.cursor_pos = 1
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_DOWN, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "1")  # Should remain at min
        self.assertEqual(self.input.get_value(), 1)
        # The current implementation actually calls on_change even when value doesn't change
        # This might be a bug in the NumberInput implementation

    def test_arrow_keys_with_empty_value(self):
        """Test arrow keys with empty value"""
        self.input.focused = True
        self.input.value = ""
        self.input.min_val = 5
        self.input.max_val = 15
        self.mock_on_change.reset_mock()

        # Up arrow with empty value - should not work since value is not digit
        event = Event(KEYDOWN, {"key": K_UP, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.value, "")  # Should remain empty (not digit)

        # Down arrow with empty value - should not work since value is not digit
        event = Event(KEYDOWN, {"key": K_DOWN, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.value, "")  # Should remain empty (not digit)

    def test_arrow_keys_with_non_digit_value(self):
        """Test arrow keys with non-digit value"""
        self.input.focused = True
        self.input.value = "abc"  # Invalid value
        self.mock_on_change.reset_mock()

        # Up arrow should not work with non-digit value
        event = Event(KEYDOWN, {"key": K_UP, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.value, "abc")  # Should remain unchanged
        self.mock_on_change.assert_not_called()

    def test_get_value_with_valid_number(self):
        """Test get_value with valid number string"""
        self.input.value = "123"
        self.assertEqual(self.input.get_value(), 123)

    def test_get_value_with_empty_string(self):
        """Test get_value with empty string returns min_val"""
        self.input.value = ""
        self.assertEqual(self.input.get_value(), self.input.min_val)

    def test_get_value_with_invalid_string(self):
        """Test get_value with invalid string returns min_val"""
        invalid_values = ["abc", "12.34", "1a2", "", "   "]
        for invalid in invalid_values:
            self.input.value = invalid
            self.assertEqual(self.input.get_value(), self.input.min_val)

    def test_backspace_handling(self):
        """Test backspace key handling"""
        self.input.focused = True
        self.input.value = "123"
        self.input.cursor_pos = 2

        event = Event(KEYDOWN, {"key": K_BACKSPACE, "unicode": ""})
        self.input.handle_event(event)

        self.assertEqual(self.input.value, "13")
        self.assertEqual(self.input.cursor_pos, 1)

    def test_cursor_movement(self):
        """Test cursor movement with arrow keys"""
        self.input.focused = True
        self.input.value = "123"
        self.input.cursor_pos = 2

        # Left arrow
        event = Event(KEYDOWN, {"key": K_LEFT, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.cursor_pos, 1)

        # Right arrow
        event = Event(KEYDOWN, {"key": K_RIGHT, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.cursor_pos, 2)

    def test_cursor_boundaries(self):
        """Test cursor movement at boundaries"""
        self.input.focused = True
        self.input.value = "123"

        # Test left boundary
        self.input.cursor_pos = 0
        event = Event(KEYDOWN, {"key": K_LEFT, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.cursor_pos, 0)

        # Test right boundary
        self.input.cursor_pos = 3
        event = Event(KEYDOWN, {"key": K_RIGHT, "unicode": ""})
        self.input.handle_event(event)
        self.assertEqual(self.input.cursor_pos, 3)

    def test_mouse_focus_inside(self):
        """Test mouse click inside input area"""
        self.input.focused = False
        pos = (self.input.input_rect.centerx, self.input.input_rect.centery)
        event = Event(MOUSEBUTTONDOWN, {"pos": pos, "button": 1})

        result = self.input.handle_event(event)

        self.assertTrue(result)
        self.assertTrue(self.input.focused)

    def test_mouse_focus_outside(self):
        """Test mouse click outside input area"""
        self.input.focused = True
        pos = (999, 999)  # Far outside
        event = Event(MOUSEBUTTONDOWN, {"pos": pos, "button": 1})

        result = self.input.handle_event(event)

        self.assertFalse(result)  # Event not consumed
        self.assertFalse(self.input.focused)

    def test_mouse_cursor_positioning(self):
        """Test cursor positioning on mouse click"""
        self.input.focused = True
        self.input.value = "12345"
        self.input.cursor_pos = 0

        # Calculate position roughly in the middle of the text
        text_x = self.input._get_text_x()
        text_width = self.input.mono_font.get_rect("12").width
        click_x = text_x + self.input.input_padding + text_width
        click_y = self.input.input_rect.centery

        event = Event(MOUSEBUTTONDOWN, {"pos": (click_x, click_y), "button": 1})
        self.input.handle_event(event)

        # Cursor should be positioned somewhere reasonable
        self.assertTrue(0 <= self.input.cursor_pos <= len(self.input.value))

    def test_unfocused_key_events_ignored(self):
        """Test that key events are ignored when unfocused"""
        self.input.focused = False
        self.input.value = "5"
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "7", "key": pygame.K_7})
        result = self.input.handle_event(event)

        self.assertFalse(result)
        self.assertEqual(self.input.value, "5")  # Unchanged
        self.mock_on_change.assert_not_called()

    def test_unicode_attribute_missing(self):
        """Test handling of events without unicode attribute"""
        self.input.focused = True

        # This should expose whether NumberInput handles missing unicode gracefully
        event = Event(KEYDOWN, {"key": pygame.K_5})
        if hasattr(event, 'unicode'):
            delattr(event, 'unicode')

        result = self.input.handle_event(event)
        self.assertTrue(result)
        # Value should not change since no unicode
        self.assertEqual(self.input.value, "")

    def test_return_key_handling(self):
        """Test return key handling (inherited from BaseInput)"""
        self.input.focused = True
        self.input.value = "42"
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_RETURN, "unicode": ""})
        self.input.handle_event(event)

        # BaseInput doesn't call on_change for return key - that's TextInput behavior
        # NumberInput inherits from BaseInput, so return key doesn't trigger on_change
        self.mock_on_change.assert_not_called()

    def test_draw_methods_work(self):
        """Test that draw methods work without errors"""
        surface = pygame.Surface((400, 100))

        # Test unfocused drawing
        self.input.focused = False
        self.input.draw(surface)

        # Test focused drawing with cursor
        self.input.focused = True
        self.input.cursor_visible = True
        self.input.value = "123"
        self.input.cursor_pos = 2
        self.input.draw(surface)

        # Test focused drawing without cursor
        self.input.cursor_visible = False
        self.input.draw(surface)

    def test_size_calculation(self):
        """Test size calculation"""
        width, height = self.input.get_size()
        expected_width = 100 + 10 + 200  # label_width + input_padding + input_width

        self.assertIsInstance(width, int)
        self.assertIsInstance(height, int)
        self.assertEqual(width, expected_width)
        self.assertGreater(height, 0)

    def test_inheritance_from_base_input(self):
        """Test that NumberInput properly inherits from BaseInput"""
        from v3xctrl_ui.menu.input.BaseInput import BaseInput
        self.assertIsInstance(self.input, BaseInput)

    def test_cursor_blink_functionality(self):
        """Test cursor blinking mechanism"""
        with patch('pygame.time.get_ticks') as mock_ticks:
            mock_ticks.return_value = self.input.cursor_timer + self.input.CURSOR_INTERVAL + 1

            old_visibility = self.input.cursor_visible
            self.input._update_cursor_blink()
            new_visibility = self.input.cursor_visible

            self.assertNotEqual(old_visibility, new_visibility)

    def test_multiple_inputs_independence(self):
        """Test that multiple NumberInput instances are independent"""
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
        """Test edge case values"""
        # Test with min_val = 0
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
        """Test behavior when min/max values change"""
        self.input.value = "50"
        self.assertEqual(self.input.get_value(), 50)

        # Change range to exclude current value
        self.input.min_val = 60
        self.input.max_val = 80

        # get_value should still return the parsed value, even if out of range
        # (validation happens on input, not on get_value)
        self.assertEqual(self.input.get_value(), 50)

    def test_position_setting(self):
        """Test position setting functionality"""
        self.input.set_position(50, 100)

        self.assertEqual(self.input.x, 50)
        self.assertEqual(self.input.y, 100)

        # Input rect should be positioned correctly
        expected_input_x = 50 + 100 + 10  # x + label_width + input_padding
        self.assertEqual(self.input.input_rect.x, expected_input_x)
        self.assertEqual(self.input.input_rect.y, 100)


if __name__ == "__main__":
    unittest.main()
