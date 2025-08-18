import unittest

import pygame
from pygame import Surface

from v3xctrl_ui.menu.DialogBox import DialogBox


class TestDialogBox(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.surface = Surface((800, 600))
        self.confirm_called = False
        self.confirm_call_count = 0

        def on_confirm():
            self.confirm_called = True
            self.confirm_call_count += 1

        self.dialog = DialogBox(
            title="Test Title",
            lines=["This is a line that should wrap properly when drawn." * 3],
            button_label="OK",
            on_confirm=on_confirm
        )

    def tearDown(self):
        pygame.quit()

    def test_initial_state(self):
        self.assertFalse(self.dialog.visible)
        self.assertEqual(self.dialog.title, "Test Title")
        self.assertEqual(self.dialog.button_label, "OK")
        self.assertIsNotNone(self.dialog.on_confirm)

    def test_visibility_toggle(self):
        self.assertFalse(self.dialog.visible)
        self.dialog.show()
        self.assertTrue(self.dialog.visible)
        self.dialog.hide()
        self.assertFalse(self.dialog.visible)

    def test_set_text_updates_lines(self):
        new_lines = ["Updated line 1", "Updated line 2"]
        self.dialog.set_text(new_lines)
        self.assertEqual(self.dialog.original_lines, new_lines)

    def test_wrap_text_with_normal_content(self):
        wrapped = self.dialog._wrap_text(200)
        self.assertIsInstance(wrapped, list)
        self.assertGreater(len(wrapped), 1)
        for line in wrapped:
            self.assertIsInstance(line, str)

    def test_wrap_text_with_empty_lines(self):
        self.dialog.set_text([])
        wrapped = self.dialog._wrap_text(200)
        self.assertIsInstance(wrapped, list)
        self.assertEqual(len(wrapped), 0)

    def test_wrap_text_with_single_word_lines(self):
        self.dialog.set_text(["Short", "Text"])
        wrapped = self.dialog._wrap_text(500)
        self.assertEqual(len(wrapped), 2)
        self.assertIn("Short", wrapped)
        self.assertIn("Text", wrapped)

    def test_wrap_text_with_very_narrow_width(self):
        wrapped = self.dialog._wrap_text(50)
        self.assertIsInstance(wrapped, list)
        self.assertGreater(len(wrapped), len(self.dialog.original_lines))

    def test_draw_when_hidden(self):
        self.dialog.hide()
        self.dialog.draw(self.surface)
        self.assertIsNone(getattr(self.dialog, 'box_rect', None))

    def test_draw_when_visible_sets_positions(self):
        self.dialog.show()
        self.dialog.draw(self.surface)

        self.assertIsNotNone(self.dialog.box_rect)
        self.assertGreater(self.dialog.box_rect.width, 0)
        self.assertGreater(self.dialog.box_rect.height, 0)

        self.assertTrue(self.dialog.button.rect.left >= self.dialog.box_rect.left)
        self.assertTrue(self.dialog.button.rect.right <= self.dialog.box_rect.right)
        self.assertTrue(self.dialog.button.rect.top >= self.dialog.box_rect.top)
        self.assertTrue(self.dialog.button.rect.bottom <= self.dialog.box_rect.bottom)

    def test_draw_centers_dialog_on_surface(self):
        self.dialog.show()
        self.dialog.draw(self.surface)

        surface_center_x = self.surface.get_width() // 2
        dialog_center_x = self.dialog.box_rect.centerx

        self.assertLess(abs(surface_center_x - dialog_center_x), 5)

    def test_button_click_calls_callback(self):
        self.dialog.show()
        self.dialog.draw(self.surface)

        self.assertTrue(self.dialog.visible)

        click_pos = self.dialog.button.rect.center

        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'button': 1,
            'pos': click_pos
        })
        self.dialog.handle_event(down_event)

        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'button': 1,
            'pos': click_pos
        })
        self.dialog.handle_event(up_event)

        self.assertTrue(self.confirm_called)
        self.assertEqual(self.confirm_call_count, 1)
        self.assertFalse(self.dialog.visible)

    def test_button_click_outside_bounds_no_callback(self):
        self.dialog.show()
        self.dialog.draw(self.surface)

        outside_pos = (0, 0)
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'button': 1,
            'pos': outside_pos
        })
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'button': 1,
            'pos': outside_pos
        })

        self.dialog.handle_event(down_event)
        self.dialog.handle_event(up_event)

        self.assertFalse(self.confirm_called)

    def test_button_drag_away_no_callback(self):
        self.dialog.show()
        self.dialog.draw(self.surface)

        button_pos = self.dialog.button.rect.center
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'button': 1,
            'pos': button_pos
        })
        self.dialog.handle_event(down_event)

        outside_pos = (0, 0)
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'button': 1,
            'pos': outside_pos
        })
        self.dialog.handle_event(up_event)

        self.assertFalse(self.confirm_called)

    def test_button_click_when_hidden_no_callback(self):
        self.dialog.hide()

        click_pos = (400, 300)
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'button': 1,
            'pos': click_pos
        })
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'button': 1,
            'pos': click_pos
        })

        self.dialog.handle_event(down_event)
        self.dialog.handle_event(up_event)

        self.assertFalse(self.confirm_called)

    def test_multiple_button_clicks(self):
        for i in range(3):
            self.dialog.show()
            self.dialog.draw(self.surface)

            click_pos = self.dialog.button.rect.center

            down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
                'button': 1,
                'pos': click_pos
            })
            up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
                'button': 1,
                'pos': click_pos
            })

            self.dialog.handle_event(down_event)
            self.dialog.handle_event(up_event)

            self.assertEqual(self.confirm_call_count, i + 1)
            self.assertFalse(self.dialog.visible)

        self.assertEqual(self.confirm_call_count, 3)

    def test_dialog_with_none_callback(self):
        dialog = DialogBox(
            title="Test",
            lines=["Test"],
            button_label="OK",
            on_confirm=None
        )
        dialog.show()
        dialog.draw(self.surface)

        click_pos = dialog.button.rect.center

        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'button': 1,
            'pos': click_pos
        })
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'button': 1,
            'pos': click_pos
        })

        dialog.handle_event(down_event)

        with self.assertRaises(TypeError):
            dialog.handle_event(up_event)

    def test_dialog_with_very_long_title(self):
        long_title = "This is a very long title that might cause issues" * 5
        dialog = DialogBox(
            title=long_title,
            lines=["Test"],
            button_label="OK",
            on_confirm=lambda: None
        )
        dialog.show()
        dialog.draw(self.surface)
        self.assertIsNotNone(dialog.box_rect)

    def test_dialog_with_many_lines(self):
        many_lines = [f"Line {i}" for i in range(50)]
        dialog = DialogBox(
            title="Test",
            lines=many_lines,
            button_label="OK",
            on_confirm=lambda: None
        )
        dialog.show()
        dialog.draw(self.surface)
        self.assertIsNotNone(dialog.box_rect)

    def test_dialog_with_empty_title(self):
        dialog = DialogBox(
            title="",
            lines=["Test"],
            button_label="OK",
            on_confirm=lambda: None
        )
        dialog.show()
        dialog.draw(self.surface)
        self.assertIsNotNone(dialog.box_rect)

    def test_dialog_with_special_characters(self):
        dialog = DialogBox(
            title="Special: àáâãäå ñ ☺",
            lines=["Special chars: àáâãäå ñ ☺ €"],
            button_label="Öķ",
            on_confirm=lambda: None
        )
        dialog.show()
        dialog.draw(self.surface)
        self.assertIsNotNone(dialog.box_rect)

    def test_button_state_management(self):
        self.dialog.show()
        self.dialog.draw(self.surface)

        hover_event = pygame.event.Event(pygame.MOUSEMOTION, {
            'pos': self.dialog.button.rect.center
        })
        self.dialog.handle_event(hover_event)

        self.assertIsNotNone(self.dialog.button)
        self.assertIsNotNone(self.dialog.button.rect)

    def test_right_mouse_button_ignored(self):
        self.dialog.show()
        self.dialog.draw(self.surface)

        click_pos = self.dialog.button.rect.center

        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'button': 3,
            'pos': click_pos
        })
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'button': 3,
            'pos': click_pos
        })

        self.dialog.handle_event(down_event)
        self.dialog.handle_event(up_event)

        self.assertFalse(self.confirm_called)

    def test_get_size_before_draw(self):
        self.assertEqual(self.dialog.get_size(), (0, 0))

    def test_get_size_after_draw(self):
        self.dialog.show()
        self.dialog.draw(self.surface)
        width, height = self.dialog.get_size()
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

    def test_wrap_text_with_word_longer_than_max_width(self):
        very_long_word = "a" * 200
        self.dialog.set_text([very_long_word])
        wrapped = self.dialog._wrap_text(50)
        self.assertGreater(len(wrapped), 0)
        self.assertIn(very_long_word, wrapped)

    def test_wrap_text_with_mixed_long_and_short_words(self):
        mixed_line = "short verylongwordthatexceedsmaxwidth short"
        self.dialog.set_text([mixed_line])
        wrapped = self.dialog._wrap_text(100)
        self.assertGreater(len(wrapped), 1)

    def test_wrap_text_empty_line_handling(self):
        self.dialog.set_text(["", "text", ""])
        wrapped = self.dialog._wrap_text(200)
        self.assertIn("text", wrapped)


class TestDialogBoxCreation(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def tearDown(self):
        pygame.quit()

    def test_create_minimal_dialog(self):
        dialog = DialogBox(
            title="Test",
            lines=["Test line"],
            button_label="OK",
            on_confirm=lambda: None
        )
        self.assertEqual(dialog.title, "Test")
        self.assertEqual(dialog.original_lines, ["Test line"])

    def test_create_dialog_with_complex_structure(self):
        complex_lines = [
            "Short line",
            "This is a much longer line that will definitely need to be wrapped when displayed",
            "",
            "Final line"
        ]
        dialog = DialogBox(
            title="Complex Dialog",
            lines=complex_lines,
            button_label="Continue",
            on_confirm=lambda: None
        )
        self.assertEqual(len(dialog.original_lines), 4)
        self.assertEqual(dialog.button_label, "Continue")


if __name__ == "__main__":
    unittest.main()
