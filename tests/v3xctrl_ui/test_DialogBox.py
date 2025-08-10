import unittest
import pygame
from pygame import Surface

from v3xctrl_ui.menu.DialogBox import DialogBox


class TestDialogBox(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.surface = Surface((800, 600))
        self.confirm_called = False

        def on_confirm():
            self.confirm_called = True

        self.dialog = DialogBox(
            title="Test Title",
            lines=["This is a line that should wrap properly when drawn." * 3],
            button_label="OK",
            on_confirm=on_confirm
        )

    def tearDown(self):
        pygame.quit()

    def test_visibility_toggle(self):
        self.assertFalse(self.dialog.visible)
        self.dialog.show()
        self.assertTrue(self.dialog.visible)
        self.dialog.hide()
        self.assertFalse(self.dialog.visible)

    def test_set_text_updates_lines(self):
        self.dialog.set_text(["Updated line 1", "Updated line 2"])
        self.assertEqual(self.dialog.original_lines, ["Updated line 1", "Updated line 2"])

    def test_wrap_text_produces_wrapped_lines(self):
        wrapped = self.dialog._wrap_text(200)
        self.assertIsInstance(wrapped, list)
        self.assertGreater(len(wrapped), 1)

    def test_draw_sets_box_rect_and_button_position(self):
        self.dialog.show()
        self.dialog.draw(self.surface)
        self.assertIsNotNone(self.dialog.box_rect)
        self.assertTrue(self.dialog.button.rect.left >= self.dialog.box_rect.left)
        self.assertTrue(self.dialog.button.rect.top >= self.dialog.box_rect.top)


if __name__ == "__main__":
    unittest.main()
