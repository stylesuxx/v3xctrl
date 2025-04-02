import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
from pygame.freetype import SysFont
from ui.menu.Checkbox import Checkbox


class TestCheckbox(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((300, 200))
        self.font = SysFont("freesansbold", 20)
        self.change_called_with = []

    def tearDown(self):
        pygame.quit()

    def on_change(self, value):
        self.change_called_with.append(value)

    def test_initialization(self):
        checkbox = Checkbox("Test", font=self.font, checked=True, on_change=self.on_change)
        self.assertEqual(checkbox.label, "Test")
        self.assertTrue(checkbox.checked)
        self.assertIsNotNone(checkbox.box_rect)
        self.assertIsNotNone(checkbox.label_rect)

    def test_draw_does_not_crash(self):
        checkbox = Checkbox("DrawTest", font=self.font, checked=False, on_change=self.on_change)
        try:
            checkbox.draw(self.screen)
        except Exception as e:
            self.fail(f"draw() raised an exception: {e}")

    def test_click_on_box_toggles_state(self):
        checkbox = Checkbox("ClickBox", font=self.font, checked=False, on_change=self.on_change)
        center = checkbox.box_rect.center
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': center, 'button': 1})
        checkbox.handle_event(event)
        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [True])

    def test_click_on_label_toggles_state(self):
        checkbox = Checkbox("ClickLabel", font=self.font, checked=False, on_change=self.on_change)
        center = checkbox.label_rect.center
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': center, 'button': 1})
        checkbox.handle_event(event)
        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [True])

    def test_click_outside_does_not_toggle(self):
        checkbox = Checkbox("OutsideClick", font=self.font, checked=False, on_change=self.on_change)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (300, 300), 'button': 1})
        checkbox.handle_event(event)
        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [])

    def test_toggle_twice(self):
        checkbox = Checkbox("Toggle", font=self.font, checked=False, on_change=self.on_change)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': checkbox.box_rect.center, 'button': 1})
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
        self.assertEqual(checkbox.label_rect.x, 50 + checkbox.BOX_SIZE + checkbox.BOX_MARGIN)


if __name__ == '__main__':
    unittest.main()
