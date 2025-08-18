import os

import unittest
from unittest.mock import MagicMock, patch

import pygame
from pygame.freetype import SysFont

from v3xctrl_ui.menu.input import Checkbox

os.environ["SDL_VIDEODRIVER"] = "dummy"


class TestCheckbox(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.freetype.init()
        self.screen = pygame.display.set_mode((300, 200))
        self.font = SysFont("freesansbold", 20)
        self.change_called_with = []

    def tearDown(self):
        pygame.freetype.quit()
        pygame.quit()

    def on_change(self, value):
        self.change_called_with.append(value)

    def test_initialization(self):
        checkbox = Checkbox("Test", font=self.font, checked=True, on_change=self.on_change)

        self.assertEqual(checkbox.label, "Test")
        self.assertTrue(checkbox.checked)
        self.assertEqual(checkbox.font, self.font)
        self.assertEqual(checkbox.on_change, self.on_change)

        self.assertIsNotNone(checkbox.box_rect)
        self.assertIsNotNone(checkbox.label_rect)
        self.assertEqual(checkbox.box_rect.width, Checkbox.BOX_SIZE)
        self.assertEqual(checkbox.box_rect.height, Checkbox.BOX_SIZE)

        self.assertTrue(checkbox.visible)
        self.assertEqual(checkbox.x, 0)
        self.assertEqual(checkbox.y, 0)

    def test_initialization_unchecked(self):
        checkbox = Checkbox("Unchecked", font=self.font, checked=False, on_change=self.on_change)
        self.assertFalse(checkbox.checked)

    def test_draw_does_not_crash(self):
        checkbox = Checkbox("DrawTest", font=self.font, checked=False, on_change=self.on_change)
        try:
            checkbox.draw(self.screen)
        except Exception as e:
            self.fail(f"draw() raised an exception: {e}")

    def test_private_draw_does_not_crash(self):
        checkbox = Checkbox("DrawTest", font=self.font, checked=False, on_change=self.on_change)
        try:
            checkbox._draw(self.screen)
        except Exception as e:
            self.fail(f"_draw() raised an exception: {e}")

    def test_click_on_box_toggles_state(self):
        checkbox = Checkbox("ClickBox", font=self.font, checked=False, on_change=self.on_change)
        center = checkbox.box_rect.center
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': center,
            'button': 1
        })
        self.assertTrue(checkbox.handle_event(event))
        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [True])

    def test_click_on_label_toggles_state(self):
        checkbox = Checkbox("ClickLabel", font=self.font, checked=False, on_change=self.on_change)
        center = checkbox.label_rect.center
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': center,
            'button': 1
        })
        self.assertTrue(checkbox.handle_event(event))
        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [True])

    def test_click_outside_does_not_toggle(self):
        checkbox = Checkbox("OutsideClick", font=self.font, checked=False, on_change=self.on_change)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (300, 300),
            'button': 1
        })
        self.assertFalse(checkbox.handle_event(event))
        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [])

    def test_right_click_ignored(self):
        checkbox = Checkbox("RightClick", font=self.font, checked=False, on_change=self.on_change)
        center = checkbox.box_rect.center
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': center,
            'button': 3
        })
        self.assertFalse(checkbox.handle_event(event))
        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [])

    def test_other_events_ignored(self):
        checkbox = Checkbox("OtherEvents", font=self.font, checked=False, on_change=self.on_change)
        keydown_event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_SPACE})
        self.assertFalse(checkbox.handle_event(keydown_event))
        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [])

    def test_toggle_twice(self):
        checkbox = Checkbox("Toggle", font=self.font, checked=False, on_change=self.on_change)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': checkbox.box_rect.center,
            'button': 1
        })

        checkbox.handle_event(event)
        checkbox.handle_event(event)

        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [True, False])

    def test_set_position_updates_layout(self):
        checkbox = Checkbox("Reposition", font=self.font, checked=False, on_change=self.on_change)
        checkbox.set_position(50, 80)

        self.assertEqual(checkbox.x, 50)
        self.assertEqual(checkbox.y, 80)

        self.assertEqual(checkbox.box_rect.topleft, (50, 80))
        expected_label_x = 50 + checkbox.BOX_SIZE + checkbox.BOX_MARGIN
        self.assertEqual(checkbox.label_rect.x, expected_label_x)

        self.assertEqual(checkbox.label_rect.centery, checkbox.box_rect.centery)

    def test_set_position_updates_basewidget_coords(self):
        checkbox = Checkbox("Position", font=self.font, checked=False, on_change=self.on_change)
        checkbox.set_position(100, 150)

        self.assertEqual(checkbox.position, (100, 150))

    def test_get_size(self):
        checkbox = Checkbox("SizeTest", font=self.font, checked=False, on_change=self.on_change)

        expected_width = checkbox.BOX_SIZE + checkbox.BOX_MARGIN + checkbox.label_rect.width
        expected_height = max(checkbox.BOX_SIZE, checkbox.label_rect.height)

        self.assertEqual(checkbox.get_size(), (expected_width, expected_height))

    def test_set_checked_method(self):
        checkbox = Checkbox("SetChecked", font=self.font, checked=False, on_change=self.on_change)

        checkbox.set_checked(True)
        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [True])

        self.change_called_with.clear()

        checkbox.set_checked(True)
        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [])

        checkbox.set_checked(False)
        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [False])

    def test_draw_checked_and_unchecked(self):
        checkbox = Checkbox("DrawTest", font=self.font, checked=False, on_change=self.on_change)

        try:
            checkbox.draw(self.screen)
        except Exception as e:
            self.fail(f"draw() raised exception when unchecked: {e}")

        checkbox.checked = True
        try:
            checkbox.draw(self.screen)
        except Exception as e:
            self.fail(f"draw() raised exception when checked: {e}")

    @patch('pygame.draw.rect')
    @patch('pygame.gfxdraw.filled_circle')
    @patch('pygame.gfxdraw.aacircle')
    def test_draw_calls_correct_methods(self, mock_aacircle, mock_filled_circle, mock_draw_rect):
        checkbox = Checkbox("DrawMethods", font=self.font, checked=True, on_change=self.on_change)
        surface = pygame.Surface((200, 100))

        checkbox._draw(surface)

        self.assertEqual(mock_draw_rect.call_count, 2)

        mock_filled_circle.assert_called_once()
        mock_aacircle.assert_called_once()

    @patch('pygame.draw.rect')
    @patch('pygame.gfxdraw.filled_circle')
    def test_draw_unchecked_no_circle(self, mock_filled_circle, mock_draw_rect):
        checkbox = Checkbox("Unchecked", font=self.font, checked=False, on_change=self.on_change)
        surface = pygame.Surface((200, 100))

        checkbox._draw(surface)

        mock_draw_rect.assert_called()

        mock_filled_circle.assert_not_called()

    def test_basewidget_inheritance(self):
        checkbox = Checkbox("BaseWidget", font=self.font, checked=False, on_change=self.on_change)
        surface = pygame.Surface((200, 100))

        checkbox.visible = True
        with patch.object(checkbox, '_draw') as mock_private_draw:
            checkbox.draw(surface)
            mock_private_draw.assert_called_once_with(surface)

        checkbox.visible = False
        with patch.object(checkbox, '_draw') as mock_private_draw:
            checkbox.draw(surface)
            mock_private_draw.assert_not_called()

    def test_width_height_properties(self):
        checkbox = Checkbox("Properties", font=self.font, checked=False, on_change=self.on_change)
        expected_width, expected_height = checkbox.get_size()

        self.assertEqual(checkbox.width, expected_width)
        self.assertEqual(checkbox.height, expected_height)

    def test_callback_with_mock(self):
        mock_callback = MagicMock()
        checkbox = Checkbox("MockCallback", font=self.font, checked=False, on_change=mock_callback)

        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': checkbox.box_rect.center,
            'button': 1
        })
        checkbox.handle_event(event)

        mock_callback.assert_called_once_with(True)

        checkbox.handle_event(event)
        self.assertEqual(mock_callback.call_count, 2)
        mock_callback.assert_called_with(False)

    def test_label_positioning_after_move(self):
        checkbox = Checkbox("LabelPos", font=self.font, checked=False, on_change=self.on_change)

        checkbox.set_position(75, 125)

        expected_label_x = 75 + Checkbox.BOX_SIZE + Checkbox.BOX_MARGIN
        self.assertEqual(checkbox.label_rect.x, expected_label_x)

        self.assertEqual(checkbox.label_rect.centery, checkbox.box_rect.centery)


if __name__ == '__main__':
    unittest.main()