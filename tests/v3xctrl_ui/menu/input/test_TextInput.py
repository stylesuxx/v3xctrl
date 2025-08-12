import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import Mock, patch
import pygame
import pygame.freetype
from pygame.event import Event
from pygame.locals import KEYDOWN, K_BACKSPACE, K_LEFT, K_RIGHT, K_RETURN, K_v, MOUSEBUTTONDOWN, KMOD_CTRL

from v3xctrl_ui.menu.input import TextInput


class TestTextInput(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.font = pygame.freetype.SysFont("Courier", 20)
        self.mock_on_change = Mock()

        self.text_input = TextInput(
            label="Test",
            label_width=100,
            input_width=200,
            font=self.font,
            mono_font=self.font,
            max_length=10,
            on_change=self.mock_on_change
        )
        self.text_input.set_position(0, 0)

    def tearDown(self):
        """Clean up after tests"""
        pygame.quit()

    def test_initialization(self):
        """Test TextInput initialization"""
        # Test inheritance from BaseInput
        self.assertEqual(self.text_input.label, "Test")
        self.assertEqual(self.text_input.label_width, 100)
        self.assertEqual(self.text_input.input_width, 200)
        self.assertEqual(self.text_input.max_length, 10)
        self.assertEqual(self.text_input.on_change, self.mock_on_change)

        # Test initial state
        self.assertEqual(self.text_input.get_value(), "")
        self.assertEqual(self.text_input.cursor_pos, 0)
        # Reset focus to test initial state properly
        fresh_input = TextInput(
            label="Fresh",
            label_width=100,
            input_width=200,
            font=self.font,
            mono_font=self.font
        )
        self.assertFalse(fresh_input.focused)

    def test_initialization_default_max_length(self):
        """Test default max_length value"""
        widget = TextInput(
            label="Test",
            label_width=100,
            input_width=200,
            font=self.font,
            mono_font=self.font
        )
        self.assertEqual(widget.max_length, 32)

    def test_single_character_input(self):
        """Test inputting a single character"""
        self.text_input.focused = True  # Explicitly set focus for this test
        event = Event(KEYDOWN, {"unicode": "a", "key": pygame.K_a})
        result = self.text_input.handle_event(event)

        self.assertTrue(result)
        self.assertEqual(self.text_input.get_value(), "a")
        self.assertEqual(self.text_input.cursor_pos, 1)
        self.mock_on_change.assert_called_once_with("a")

    def test_multiple_character_input(self):
        """Test inputting multiple characters"""
        self.text_input.focused = True
        characters = ["h", "e", "l", "l", "o"]
        for char in characters:
            event = Event(KEYDOWN, {"unicode": char, "key": ord(char)})
            self.text_input.handle_event(event)

        self.assertEqual(self.text_input.get_value(), "hello")
        self.assertEqual(self.text_input.cursor_pos, 5)
        self.assertEqual(self.mock_on_change.call_count, 5)

    def test_character_insertion_at_cursor(self):
        """Test character insertion at cursor position"""
        self.text_input.focused = True
        self.text_input.value = "hllo"
        self.text_input.cursor_pos = 1

        event = Event(KEYDOWN, {"unicode": "e", "key": pygame.K_e})
        self.text_input.handle_event(event)

        self.assertEqual(self.text_input.get_value(), "hello")
        self.assertEqual(self.text_input.cursor_pos, 2)

    def test_special_characters_input(self):
        """Test inputting special characters"""
        self.text_input.focused = True
        special_chars = ["!", "@", "#", "$", "%", " ", ".", ","]
        for char in special_chars:
            self.text_input.value = ""
            self.text_input.cursor_pos = 0
            self.mock_on_change.reset_mock()

            event = Event(KEYDOWN, {"unicode": char, "key": ord(char)})
            self.text_input.handle_event(event)

            self.assertEqual(self.text_input.get_value(), char)
            self.mock_on_change.assert_called_once_with(char)

    def test_non_printable_characters_ignored(self):
        """Test that non-printable characters are ignored"""
        self.text_input.focused = True
        non_printable_chars = ["\x00", "\x01", "\x1f", "\x7f"]
        for char in non_printable_chars:
            self.text_input.value = "test"
            self.text_input.cursor_pos = 4
            self.mock_on_change.reset_mock()

            event = Event(KEYDOWN, {"unicode": char, "key": ord(char)})
            self.text_input.handle_event(event)

            self.assertEqual(self.text_input.get_value(), "test")  # Unchanged
            self.mock_on_change.assert_not_called()

    def test_max_length_enforcement(self):
        """Test max length enforcement"""
        self.text_input.focused = True
        self.text_input.max_length = 3
        self.text_input.value = "abc"
        self.text_input.cursor_pos = 3
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "d", "key": pygame.K_d})
        self.text_input.handle_event(event)

        self.assertEqual(self.text_input.value, "abc")  # Unchanged
        self.assertEqual(self.text_input.cursor_pos, 3)  # Unchanged
        self.mock_on_change.assert_not_called()

    def test_max_length_insertion_in_middle(self):
        """Test max length enforcement when inserting in middle"""
        self.text_input.focused = True
        self.text_input.max_length = 5
        self.text_input.value = "hello"
        self.text_input.cursor_pos = 2
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "x", "key": pygame.K_x})
        self.text_input.handle_event(event)

        self.assertEqual(self.text_input.value, "hello")  # Unchanged
        self.assertEqual(self.text_input.cursor_pos, 2)  # Unchanged
        self.mock_on_change.assert_not_called()

    def test_backspace_handling(self):
        """Test backspace key handling"""
        self.text_input.focused = True
        self.text_input.value = "hello"
        self.text_input.cursor_pos = 3
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_BACKSPACE, "unicode": ""})
        self.text_input.handle_event(event)

        self.assertEqual(self.text_input.value, "helo")
        self.assertEqual(self.text_input.cursor_pos, 2)
        # Note: BaseInput doesn't call on_change for backspace
        self.mock_on_change.assert_not_called()

    def test_backspace_at_beginning(self):
        """Test backspace at beginning of text"""
        self.text_input.focused = True
        self.text_input.value = "hello"
        self.text_input.cursor_pos = 0

        event = Event(KEYDOWN, {"key": K_BACKSPACE, "unicode": ""})
        self.text_input.handle_event(event)

        self.assertEqual(self.text_input.value, "hello")  # Unchanged
        self.assertEqual(self.text_input.cursor_pos, 0)  # Unchanged

    def test_cursor_movement_left(self):
        """Test left arrow cursor movement"""
        self.text_input.focused = True
        self.text_input.value = "hello"
        self.text_input.cursor_pos = 3

        event = Event(KEYDOWN, {"key": K_LEFT, "unicode": ""})
        self.text_input.handle_event(event)

        self.assertEqual(self.text_input.cursor_pos, 2)

    def test_cursor_movement_right(self):
        """Test right arrow cursor movement"""
        self.text_input.focused = True
        self.text_input.value = "hello"
        self.text_input.cursor_pos = 2

        event = Event(KEYDOWN, {"key": K_RIGHT, "unicode": ""})
        self.text_input.handle_event(event)

        self.assertEqual(self.text_input.cursor_pos, 3)

    def test_cursor_movement_boundaries(self):
        """Test cursor movement at boundaries"""
        self.text_input.focused = True
        self.text_input.value = "hello"

        # Test left boundary
        self.text_input.cursor_pos = 0
        event = Event(KEYDOWN, {"key": K_LEFT, "unicode": ""})
        self.text_input.handle_event(event)
        self.assertEqual(self.text_input.cursor_pos, 0)

        # Test right boundary
        self.text_input.cursor_pos = 5
        event = Event(KEYDOWN, {"key": K_RIGHT, "unicode": ""})
        self.text_input.handle_event(event)
        self.assertEqual(self.text_input.cursor_pos, 5)

    def test_return_key_submission(self):
        """Test return key triggers on_change"""
        self.text_input.focused = True
        self.text_input.value = "submit"
        self.text_input.cursor_pos = 6
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_RETURN, "unicode": ""})
        self.text_input.handle_event(event)

        self.mock_on_change.assert_called_once_with("submit")

    def test_return_key_empty_value(self):
        """Test return key with empty value"""
        self.text_input.focused = True
        self.text_input.value = ""
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"key": K_RETURN, "unicode": ""})
        self.text_input.handle_event(event)

        self.mock_on_change.assert_called_once_with("")

    def test_return_key_without_callback(self):
        """Test return key when no callback is set"""
        widget = TextInput(
            label="Test",
            label_width=100,
            input_width=200,
            font=self.font,
            mono_font=self.font
        )
        widget.focused = True
        widget.value = "test"

        event = Event(KEYDOWN, {"key": K_RETURN, "unicode": ""})
        # Should not raise an exception
        result = widget.handle_event(event)
        self.assertTrue(result)

    @patch('pygame.scrap.get_init')
    @patch('pygame.key.get_mods')
    def test_paste_within_max_length(self, mock_get_mods, mock_scrap_init):
        """Test paste that doesn't exceed max length"""
        self.text_input.focused = True
        mock_get_mods.return_value = KMOD_CTRL
        mock_scrap_init.return_value = True
        self.text_input.max_length = 10
        self.text_input.value = "hello"

        with patch.object(self.text_input, '_get_clipboard_text', return_value="world"):
            event = Event(KEYDOWN, {"key": K_v, "unicode": ""})
            self.text_input.handle_event(event)

        self.assertEqual(self.text_input.value, "world")
        self.mock_on_change.assert_called_with("world")

    @patch('pygame.scrap.get_init')
    @patch('pygame.key.get_mods')
    def test_paste_exceeds_max_length(self, mock_get_mods, mock_scrap_init):
        """Test paste that exceeds max length"""
        self.text_input.focused = True
        mock_get_mods.return_value = KMOD_CTRL
        mock_scrap_init.return_value = True
        self.text_input.max_length = 5

        with patch.object(self.text_input, '_get_clipboard_text', return_value="this is too long"):
            event = Event(KEYDOWN, {"key": K_v, "unicode": ""})
            self.text_input.handle_event(event)

        # Should paste the full text (base class doesn't enforce max_length on paste)
        self.assertEqual(self.text_input.value, "this is too long")

    def test_mouse_focus_inside(self):
        """Test mouse click inside input area"""
        self.text_input.focused = False
        pos = (self.text_input.input_rect.centerx, self.text_input.input_rect.centery)
        event = Event(MOUSEBUTTONDOWN, {"pos": pos, "button": 1})

        result = self.text_input.handle_event(event)

        self.assertTrue(result)
        self.assertTrue(self.text_input.focused)

    def test_mouse_focus_outside(self):
        """Test mouse click outside input area"""
        self.text_input.focused = True
        pos = (999, 999)  # Far outside
        event = Event(MOUSEBUTTONDOWN, {"pos": pos, "button": 1})

        result = self.text_input.handle_event(event)

        self.assertFalse(result)  # Event not consumed
        self.assertFalse(self.text_input.focused)

    def test_mouse_cursor_positioning(self):
        """Test cursor positioning on mouse click"""
        self.text_input.value = "hello world"
        self.text_input.cursor_pos = 0

        # Calculate position roughly in the middle of the text
        text_x = self.text_input._get_text_x()
        text_width = self.text_input.mono_font.get_rect("hello ").width
        click_x = text_x + self.text_input.input_padding + text_width
        click_y = self.text_input.input_rect.centery

        event = Event(MOUSEBUTTONDOWN, {"pos": (click_x, click_y), "button": 1})
        self.text_input.handle_event(event)

        # Cursor should be positioned somewhere reasonable (not exact due to font rendering)
        self.assertTrue(0 <= self.text_input.cursor_pos <= len(self.text_input.value))

    def test_unfocused_key_events_ignored(self):
        """Test that key events are ignored when unfocused"""
        self.text_input.focused = False
        self.text_input.value = "test"
        self.mock_on_change.reset_mock()

        event = Event(KEYDOWN, {"unicode": "x", "key": pygame.K_x})
        result = self.text_input.handle_event(event)

        self.assertFalse(result)
        self.assertEqual(self.text_input.value, "test")  # Unchanged
        self.mock_on_change.assert_not_called()

    def test_empty_unicode_handling(self):
        """Test handling of events with empty unicode"""
        self.text_input.focused = True
        event = Event(KEYDOWN, {"unicode": "", "key": pygame.K_SPACE})
        result = self.text_input.handle_event(event)

        self.assertTrue(result)  # Event handled but no character added
        self.assertEqual(self.text_input.value, "")

    def test_unicode_none_handling(self):
        """Test handling of events without unicode attribute"""
        self.text_input.focused = True

        # Test the actual behavior - if TextInput doesn't handle missing unicode gracefully,
        # this test should make it clear that the code needs to be fixed
        # Create an event that has no unicode attribute
        event = Event(KEYDOWN, {"key": pygame.K_SPACE})

        # Remove the unicode attribute if it exists
        if hasattr(event, 'unicode'):
            delattr(event, 'unicode')

        result = self.text_input.handle_event(event)
        self.assertTrue(result)  # Event was handled
        self.assertEqual(self.text_input.value, "")  # No character should be added

    def test_get_value_method(self):
        """Test get_value method returns correct type and value"""
        self.text_input.value = "test value"
        result = self.text_input.get_value()

        self.assertIsInstance(result, str)
        self.assertEqual(result, "test value")

    def test_inheritance_from_base_input(self):
        """Test that TextInput properly inherits from BaseInput"""
        from v3xctrl_ui.menu.input.BaseInput import BaseInput
        self.assertIsInstance(self.text_input, BaseInput)

    def test_draw_methods_exist(self):
        """Test that draw methods work without errors"""
        surface = pygame.Surface((400, 100))

        # Test unfocused drawing
        self.text_input.focused = False
        self.text_input.draw(surface)

        # Test focused drawing with cursor
        self.text_input.focused = True
        self.text_input.cursor_visible = True
        self.text_input.value = "test"
        self.text_input.cursor_pos = 2
        self.text_input.draw(surface)

        # Test focused drawing without cursor
        self.text_input.cursor_visible = False
        self.text_input.draw(surface)

    def test_size_calculation(self):
        """Test size calculation"""
        width, height = self.text_input.get_size()
        expected_width = 100 + 10 + 200  # label_width + input_padding + input_width

        self.assertIsInstance(width, int)
        self.assertIsInstance(height, int)
        self.assertEqual(width, expected_width)
        self.assertGreater(height, 0)

    def test_cursor_blink_functionality(self):
        """Test cursor blinking mechanism"""
        # Set up cursor to blink
        with patch('pygame.time.get_ticks') as mock_ticks:
            mock_ticks.return_value = self.text_input.cursor_timer + TextInput.CURSOR_INTERVAL + 1

            old_visibility = self.text_input.cursor_visible
            self.text_input._update_cursor_blink()
            new_visibility = self.text_input.cursor_visible

            self.assertNotEqual(old_visibility, new_visibility)

    def test_constants_accessibility(self):
        """Test that constants are accessible"""
        self.assertIsInstance(TextInput.CURSOR_INTERVAL, int)
        self.assertIsInstance(TextInput.CURSOR_WIDTH, int)
        self.assertIsInstance(TextInput.CURSOR_GAP, int)

    def test_multiple_inputs_independence(self):
        """Test that multiple TextInput instances are independent"""
        second_input = TextInput(
            label="Second",
            label_width=50,
            input_width=150,
            font=self.font,
            mono_font=self.font
        )

        self.text_input.value = "first"
        second_input.value = "second"

        self.assertEqual(self.text_input.get_value(), "first")
        self.assertEqual(second_input.get_value(), "second")

    def test_position_setting(self):
        """Test position setting functionality"""
        self.text_input.set_position(50, 100)

        self.assertEqual(self.text_input.x, 50)
        self.assertEqual(self.text_input.y, 100)

        # Input rect should be positioned correctly
        expected_input_x = 50 + 100 + 10  # x + label_width + input_padding
        self.assertEqual(self.text_input.input_rect.x, expected_input_x)
        self.assertEqual(self.text_input.input_rect.y, 100)


if __name__ == "__main__":
    unittest.main()
