# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame
from pygame.freetype import Font

from v3xctrl_ui.menu.input.BaseInput import BaseInput


class TestBaseInput(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.freetype.init()

        self.mock_font = MagicMock(spec=Font)
        self.mock_mono_font = MagicMock(spec=Font)

        self.mock_font.size = 16
        mock_surface = pygame.Surface((100, 16))
        mock_rect = pygame.Rect(0, 0, 100, 16)
        self.mock_font.render.return_value = (mock_surface, mock_rect)
        self.mock_font.get_rect.return_value = mock_rect

        self.mock_mono_font.size = 14
        mono_surface = pygame.Surface((80, 14))
        mono_rect = pygame.Rect(0, 0, 80, 14)
        self.mock_mono_font.render.return_value = (mono_surface, mono_rect)
        self.mock_mono_font.get_rect.return_value = mono_rect

        self.mock_on_change = MagicMock()

        self.input_widget = BaseInput(
            label="Test Label",
            label_width=100,
            input_width=200,
            font=self.mock_font,
            mono_font=self.mock_mono_font,
            on_change=self.mock_on_change,
            input_padding=10
        )

    def test_initialization(self):
        self.assertEqual(self.input_widget.label, "Test Label")
        self.assertEqual(self.input_widget.label_width, 100)
        self.assertEqual(self.input_widget.input_width, 200)
        self.assertEqual(self.input_widget.font, self.mock_font)
        self.assertEqual(self.input_widget.mono_font, self.mock_mono_font)
        self.assertEqual(self.input_widget.on_change, self.mock_on_change)
        self.assertEqual(self.input_widget.input_padding, 10)

        self.assertEqual(self.input_widget.value, "")
        self.assertEqual(self.input_widget.cursor_pos, 0)
        self.assertFalse(self.input_widget.focused)
        self.assertTrue(self.input_widget.cursor_visible)
        self.assertEqual(self.input_widget.cursor_timer, 0)

        expected_height = self.mock_font.size + 10
        self.assertEqual(self.input_widget.input_height, expected_height)

        self.assertIsInstance(self.input_widget.input_rect, pygame.Rect)
        self.assertEqual(self.input_widget.input_rect.width, 200)
        self.assertEqual(self.input_widget.input_rect.height, expected_height)

        self.assertIsInstance(self.input_widget.input_surface, pygame.Surface)

    def test_initialization_without_callback(self):
        widget = BaseInput(
            label="Test",
            label_width=50,
            input_width=100,
            font=self.mock_font,
            mono_font=self.mock_mono_font
        )

        self.assertIsNone(widget.on_change)

    def test_set_position(self):
        self.input_widget.set_position(50, 100)

        self.assertEqual(self.input_widget.x, 50)
        self.assertEqual(self.input_widget.y, 100)

        expected_input_x = 50 + 100 + 10
        self.assertEqual(self.input_widget.input_rect.x, expected_input_x)
        self.assertEqual(self.input_widget.input_rect.y, 100)

        expected_cursor_y_start = 100 + (self.input_widget.input_rect.height - self.input_widget.cursor_height) // 2
        self.assertEqual(self.input_widget.cursor_y_start, expected_cursor_y_start)
        self.assertEqual(self.input_widget.cursor_y_end, expected_cursor_y_start + self.input_widget.cursor_height)

    def test_get_size(self):
        width, height = self.input_widget.get_size()

        expected_width = 100 + 10 + 200
        expected_height = self.input_widget.input_rect.height

        self.assertEqual(width, expected_width)
        self.assertEqual(height, expected_height)

    def test_get_value(self):
        self.input_widget.value = "test value"
        self.assertEqual(self.input_widget.get_value(), "test value")

        self.input_widget.value = ""
        self.assertEqual(self.input_widget.get_value(), "")

    @patch('pygame.time.get_ticks')
    def test_update_cursor_blink(self, mock_get_ticks):
        self.input_widget.cursor_visible = True
        self.input_widget.cursor_timer = 0

        mock_get_ticks.return_value = 400
        self.input_widget._update_cursor_blink()
        self.assertTrue(self.input_widget.cursor_visible)

        mock_get_ticks.return_value = 500
        self.input_widget._update_cursor_blink()
        self.assertFalse(self.input_widget.cursor_visible)
        self.assertEqual(self.input_widget.cursor_timer, 500)

        mock_get_ticks.return_value = 1000
        self.input_widget._update_cursor_blink()
        self.assertTrue(self.input_widget.cursor_visible)
        self.assertEqual(self.input_widget.cursor_timer, 1000)

    def test_get_text_x(self):
        self.input_widget.set_position(0, 0)
        self.input_widget.value = "test"

        self.mock_mono_font.get_rect.return_value.width = 40

        expected_x = self.input_widget.input_rect.right - 10 - 40
        actual_x = self.input_widget._get_text_x()

        self.assertEqual(actual_x, expected_x)

    @patch('pygame.time.get_ticks')
    def test_handle_mouse_cursor_position(self, mock_get_ticks):
        mock_get_ticks.return_value = 1000
        self.input_widget.set_position(0, 0)
        self.input_widget.value = "hello"

        self.mock_mono_font.get_rect.side_effect = lambda text: type('MockRect', (), {'width': len(text) * 8})()

        with patch.object(self.input_widget, '_get_text_x', return_value=100):
            mouse_pos = (116, 10)
            self.input_widget._handle_mouse(mouse_pos)

            self.assertEqual(self.input_widget.cursor_timer, 1000)

    def test_handle_event_mouse_click_inside(self):
        self.input_widget.set_position(0, 0)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'button': 1,
            'pos': (150, 10)
        })

        with patch.object(self.input_widget, '_handle_mouse') as mock_handle_mouse:
            self.assertTrue(self.input_widget.handle_event(event))
            mock_handle_mouse.assert_called_once_with((150, 10))
            self.assertTrue(self.input_widget.focused)

    def test_handle_event_mouse_click_outside(self):
        self.input_widget.set_position(0, 0)
        self.input_widget.focused = True

        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'button': 1,
            'pos': (50, 10)
        })

        with patch.object(self.input_widget, '_handle_mouse') as mock_handle_mouse:
            self.assertFalse(self.input_widget.handle_event(event))
            mock_handle_mouse.assert_not_called()
            self.assertFalse(self.input_widget.focused)

    def test_handle_event_mouse_right_click(self):
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'button': 3,
            'pos': (100, 50)
        })

        with patch.object(self.input_widget, '_handle_mouse') as mock_handle_mouse:
            self.assertFalse(self.input_widget.handle_event(event))
            mock_handle_mouse.assert_not_called()

    def test_handle_event_keydown_unfocused(self):
        self.input_widget.focused = False
        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_a
        })

        with patch.object(self.input_widget, '_handle_keydown') as mock_handle_keydown:
            self.assertFalse(self.input_widget.handle_event(event))
            mock_handle_keydown.assert_not_called()

    def test_handle_event_keydown_focused(self):
        self.input_widget.focused = True
        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_a
        })

        with patch.object(self.input_widget, '_handle_keydown') as mock_handle_keydown:
            self.assertTrue(self.input_widget.handle_event(event))
            mock_handle_keydown.assert_called_once_with(event)

    def test_handle_event_other_types(self):
        event = pygame.event.Event(pygame.KEYUP, {
            'key': pygame.K_a
        })

        with patch.object(self.input_widget, '_handle_mouse') as mock_handle_mouse, \
             patch.object(self.input_widget, '_handle_keydown') as mock_handle_keydown:

            self.assertFalse(self.input_widget.handle_event(event))
            mock_handle_mouse.assert_not_called()
            mock_handle_keydown.assert_not_called()

    @patch('pygame.key.get_mods')
    def test_handle_keydown_backspace(self, mock_get_mods):
        mock_get_mods.return_value = 0
        self.input_widget.value = "hello"
        self.input_widget.cursor_pos = 3

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_BACKSPACE
        })

        self.input_widget._handle_keydown(event)

        self.assertEqual(self.input_widget.value, "helo")
        self.assertEqual(self.input_widget.cursor_pos, 2)

    @patch('pygame.key.get_mods')
    def test_handle_keydown_backspace_at_start(self, mock_get_mods):
        mock_get_mods.return_value = 0
        self.input_widget.value = "hello"
        self.input_widget.cursor_pos = 0

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_BACKSPACE
        })

        self.input_widget._handle_keydown(event)

        self.assertEqual(self.input_widget.value, "hello")
        self.assertEqual(self.input_widget.cursor_pos, 0)

    @patch('pygame.key.get_mods')
    def test_handle_keydown_left_arrow(self, mock_get_mods):
        mock_get_mods.return_value = 0
        self.input_widget.value = "hello"
        self.input_widget.cursor_pos = 3

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_LEFT
        })

        self.input_widget._handle_keydown(event)

        self.assertEqual(self.input_widget.cursor_pos, 2)

    @patch('pygame.key.get_mods')
    def test_handle_keydown_left_arrow_at_start(self, mock_get_mods):
        mock_get_mods.return_value = 0
        self.input_widget.cursor_pos = 0

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_LEFT
        })

        self.input_widget._handle_keydown(event)

        self.assertEqual(self.input_widget.cursor_pos, 0)

    @patch('pygame.key.get_mods')
    def test_handle_keydown_right_arrow(self, mock_get_mods):
        mock_get_mods.return_value = 0
        self.input_widget.value = "hello"
        self.input_widget.cursor_pos = 3

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_RIGHT
        })

        self.input_widget._handle_keydown(event)

        self.assertEqual(self.input_widget.cursor_pos, 4)

    @patch('pygame.key.get_mods')
    def test_handle_keydown_right_arrow_at_end(self, mock_get_mods):
        mock_get_mods.return_value = 0
        self.input_widget.value = "hello"
        self.input_widget.cursor_pos = 5

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_RIGHT
        })

        self.input_widget._handle_keydown(event)

        self.assertEqual(self.input_widget.cursor_pos, 5)

    @patch('pygame.scrap.get_init')
    @patch('pygame.key.get_mods')
    def test_handle_keydown_paste_not_initialized(self, mock_get_mods, mock_scrap_init):
        mock_get_mods.return_value = pygame.KMOD_CTRL
        mock_scrap_init.return_value = False
        self.input_widget.value = "hello"

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_v
        })

        self.input_widget._handle_keydown(event)

        self.assertEqual(self.input_widget.value, "hello")

    @patch('pygame.scrap.get_init')
    @patch('pygame.key.get_mods')
    def test_handle_keydown_paste_with_text(self, mock_get_mods, mock_scrap_init):
        mock_get_mods.return_value = pygame.KMOD_CTRL
        mock_scrap_init.return_value = True
        self.input_widget.value = "hello"
        self.input_widget.cursor_pos = 2

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_v
        })

        with patch.object(self.input_widget, '_get_clipboard_text', return_value="pasted"):
            self.input_widget._handle_keydown(event)

        self.assertEqual(self.input_widget.value, "pasted")
        self.assertEqual(self.input_widget.cursor_pos, 6)
        self.mock_on_change.assert_called_once_with("pasted")

    @patch('pygame.scrap.get_init')
    @patch('pygame.key.get_mods')
    def test_handle_keydown_paste_no_text(self, mock_get_mods, mock_scrap_init):
        mock_get_mods.return_value = pygame.KMOD_CTRL
        mock_scrap_init.return_value = True
        self.input_widget.value = "hello"

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_v
        })

        with patch.object(self.input_widget, '_get_clipboard_text', return_value=None):
            self.input_widget._handle_keydown(event)

        self.assertEqual(self.input_widget.value, "hello")
        self.mock_on_change.assert_not_called()

    @patch('pygame.scrap.get_types')
    @patch('pygame.scrap.get')
    def test_get_clipboard_text_success(self, mock_scrap_get, mock_get_types):
        mock_get_types.return_value = ["text/plain;charset=utf-8"]
        mock_scrap_get.return_value = b"clipboard text"

        self.assertEqual(self.input_widget._get_clipboard_text(), "clipboard text")

    @patch('pygame.scrap.get_types')
    @patch('pygame.scrap.get')
    def test_get_clipboard_text_string_data(self, mock_scrap_get, mock_get_types):
        mock_get_types.return_value = ["text/plain"]
        mock_scrap_get.return_value = "  clipboard text  "

        self.assertEqual(self.input_widget._get_clipboard_text(), "clipboard text")

    @patch('pygame.scrap.get_types')
    @patch('pygame.scrap.get')
    def test_get_clipboard_text_no_data(self, mock_scrap_get, mock_get_types):
        mock_get_types.return_value = ["text/plain"]
        mock_scrap_get.return_value = None

        self.assertIsNone(self.input_widget._get_clipboard_text())

    @patch('pygame.scrap.get_types')
    @patch('pygame.scrap.get')
    def test_get_clipboard_text_empty_after_decode(self, mock_scrap_get, mock_get_types):
        mock_get_types.return_value = ["text/plain", "text/plain;charset=utf-8"]

        def side_effect(type_name):
            if type_name == "text/plain":
                return b''
            elif type_name == "text/plain;charset=utf-8":
                return b'valid text'
            return None

        mock_scrap_get.side_effect = side_effect

        self.assertEqual(self.input_widget._get_clipboard_text(), "valid text")

    @patch('pygame.scrap.get_types')
    @patch('pygame.scrap.get')
    def test_get_clipboard_text_actual_unicode_error(self, mock_scrap_get, mock_get_types):
        mock_get_types.return_value = ["text/plain", "text/plain;charset=utf-8"]

        class BadBytes(bytes):
            def decode(self, encoding='utf-8', errors='strict'):
                raise UnicodeDecodeError('utf-8', self, 0, 1, 'mock error')

        def side_effect(type_name):
            if type_name == "text/plain":
                return BadBytes(b'bad data')
            elif type_name == "text/plain;charset=utf-8":
                return b'valid text'
            return None

        mock_scrap_get.side_effect = side_effect

        self.assertEqual(self.input_widget._get_clipboard_text(), "valid text")

    @patch('pygame.scrap.get_types')
    def test_get_clipboard_text_no_text_types(self, mock_get_types):
        mock_get_types.return_value = ["image/png", "application/json"]

        self.assertIsNone(self.input_widget._get_clipboard_text())

    def test_draw_basic(self):
        surface = pygame.Surface((400, 100))
        self.input_widget.set_position(10, 10)
        self.input_widget.value = "test"

        with patch.object(self.input_widget, '_update_cursor_blink'):
            self.input_widget._draw(surface)

        self.mock_mono_font.render.assert_called_with("test", BaseInput.TEXT_COLOR)

    @patch('pygame.draw.line')
    def test_draw_with_cursor(self, mock_draw_line):
        surface = pygame.Surface((400, 100))
        self.input_widget.set_position(10, 10)
        self.input_widget.value = "test"
        self.input_widget.focused = True
        self.input_widget.cursor_visible = True
        self.input_widget.cursor_pos = 2

        self.text_surface = pygame.Surface((50, 14))
        self.text_rect = pygame.Rect(0, 0, 50, 14)
        self.text_rect.right = 200
        self.text_rect.centery = 20
        self.mock_mono_font.render.return_value = (self.text_surface, self.text_rect)

        mock_rect = type('MockRect', (), {'width': 16})()
        self.mock_mono_font.get_rect.return_value = mock_rect

        with patch.object(self.input_widget, '_update_cursor_blink'):
            self.input_widget.draw(surface)

        mock_draw_line.assert_called_once()

    def test_draw_without_cursor(self):
        surface = pygame.Surface((400, 100))
        self.input_widget.set_position(10, 10)
        self.input_widget.value = "test"
        self.input_widget.focused = False

        with patch('pygame.draw.line') as mock_draw_line, \
             patch.object(self.input_widget, '_update_cursor_blink'):

            self.input_widget._draw(surface)

        mock_draw_line.assert_not_called()

    def test_draw_input_background(self):
        with patch('pygame.draw.line') as mock_draw_line:
            self.input_widget._draw_input_background()

        self.assertEqual(mock_draw_line.call_count, 4)

    def test_private_draw_method(self):
        surface = pygame.Surface((400, 100))
        self.input_widget.set_position(10, 10)

        with patch.object(self.input_widget, '_update_cursor_blink'):
            self.input_widget._draw(surface)

    def test_public_draw_method_when_visible(self):
        surface = pygame.Surface((400, 100))
        self.input_widget.set_position(10, 10)
        self.input_widget.visible = True

        with patch.object(self.input_widget, '_draw') as mock_private_draw:
            self.input_widget.draw(surface)
            mock_private_draw.assert_called_once_with(surface)

    def test_public_draw_method_when_invisible(self):
        surface = pygame.Surface((400, 100))
        self.input_widget.set_position(10, 10)
        self.input_widget.visible = False

        with patch.object(self.input_widget, '_draw') as mock_private_draw:
            self.input_widget.draw(surface)
            mock_private_draw.assert_not_called()

    def test_widget_properties(self):
        self.input_widget.set_position(100, 200)

        self.assertEqual(self.input_widget.position, (100, 200))

        expected_width, expected_height = self.input_widget.get_size()
        self.assertEqual(self.input_widget.width, expected_width)
        self.assertEqual(self.input_widget.height, expected_height)

        self.assertTrue(self.input_widget.visible)

    def test_abstract_methods_implemented(self):
        event = pygame.event.Event(pygame.KEYUP, {
            'key': pygame.K_a
        })

        self.assertIsInstance(self.input_widget.handle_event(event), bool)

        surface = pygame.Surface((100, 100))
        with patch.object(self.input_widget, '_update_cursor_blink'):
            self.input_widget._draw(surface)

        size = self.input_widget.get_size()
        self.assertIsInstance(size, tuple)
        self.assertEqual(len(size), 2)

    def test_on_change_callback_on_backspace(self):
        self.input_widget.value = "hello"
        self.input_widget.cursor_pos = 3

        event = pygame.event.Event(pygame.KEYDOWN, {
            'key': pygame.K_BACKSPACE
        })

        with patch('pygame.key.get_mods', return_value=0):
            self.input_widget._handle_keydown(event)

        self.mock_on_change.assert_called_once_with("helo")

    def test_text_caching_optimization(self):
        surface = pygame.Surface((400, 100))
        self.input_widget.set_position(10, 10)
        self.input_widget.value = "test"

        with patch.object(self.input_widget, '_update_cursor_blink'):
            self.input_widget._draw(surface)
            first_call_count = self.mock_mono_font.render.call_count

            self.input_widget._draw(surface)
            second_call_count = self.mock_mono_font.render.call_count

            self.assertEqual(first_call_count, second_call_count)

            self.input_widget.value = "changed"
            self.input_widget._draw(surface)
            third_call_count = self.mock_mono_font.render.call_count

            self.assertGreater(third_call_count, second_call_count)

    def test_handle_mouse_uses_input_padding(self):
        self.input_widget.set_position(0, 0)
        self.input_widget.value = "hello"
        self.input_widget.input_padding = 15

        self.mock_mono_font.get_rect.side_effect = lambda text: type('MockRect', (), {'width': len(text) * 8})()

        with patch.object(self.input_widget, '_get_text_x', return_value=100) as mock_get_text_x:
            mouse_pos = (130, 10)
            self.input_widget._handle_mouse(mouse_pos)

            mock_get_text_x.assert_called_once()

            self.assertTrue(self.input_widget.cursor_visible)


if __name__ == '__main__':
    unittest.main()
