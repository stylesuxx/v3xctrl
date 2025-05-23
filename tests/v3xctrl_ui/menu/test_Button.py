import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
import pygame.freetype
import unittest
from unittest.mock import MagicMock

from v3xctrl_ui.menu.Button import Button


class TestButton(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.font.init()
        self.screen = pygame.Surface((300, 200))
        self.font = pygame.freetype.SysFont("freesansbold", 30)
        self.callback = MagicMock()
        self.button = Button("Test", 100, 40, self.font, self.callback)
        self.button.set_position(50, 50)

    def tearDown(self):
        pygame.quit()

    def test_hover_state_true(self):
        event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (60, 60)})
        self.button.handle_event(event)
        self.assertTrue(self.button.hovered)

    def test_hover_state_false(self):
        event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (10, 10)})
        self.button.handle_event(event)
        self.assertFalse(self.button.hovered)

    def test_active_on_click_inside(self):
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (60, 60), 'button': 1})
        self.button.handle_event(down_event)
        self.assertTrue(self.button.active)

    def test_callback_on_release_inside(self):
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (60, 60), 'button': 1})
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (60, 60), 'button': 1})
        self.button.handle_event(down_event)
        self.button.handle_event(up_event)
        self.callback.assert_called_once()
        self.assertFalse(self.button.active)

    def test_no_callback_on_release_outside(self):
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (60, 60), 'button': 1})
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (10, 10), 'button': 1})
        self.button.handle_event(down_event)
        self.button.handle_event(up_event)
        self.callback.assert_not_called()
        self.assertFalse(self.button.active)

    def test_disabled_button_ignores_events(self):
        self.button.disable()
        motion_event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (60, 60)})
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (60, 60), 'button': 1})
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (60, 60), 'button': 1})

        self.button.handle_event(motion_event)
        self.button.handle_event(down_event)
        self.button.handle_event(up_event)

        self.assertFalse(self.button.hovered)
        self.assertFalse(self.button.active)
        self.callback.assert_not_called()

    def test_enable_disable_toggle(self):
        self.button.disable()
        self.assertTrue(self.button.disabled)

        self.button.enable()
        self.assertFalse(self.button.disabled)

    def test_draw_does_not_crash(self):
        try:
            self.button.draw(self.screen)
        except Exception as e:
            self.fail(f"Button.draw() raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()
