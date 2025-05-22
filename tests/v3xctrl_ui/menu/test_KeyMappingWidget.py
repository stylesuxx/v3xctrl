import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
import pygame.freetype
from unittest.mock import MagicMock

from v3xctrl_ui.menu.KeyMappingWidget import KeyMappingWidget


class TestKeyMappingWidget(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.font = pygame.freetype.SysFont("freesansbold", 20)
        self.on_key_change = MagicMock()
        self.on_remap_toggle = MagicMock()

        self.widget = KeyMappingWidget(
            control_name="throttle_up",
            key_code=pygame.K_w,
            font=self.font,
            on_key_change=self.on_key_change,
            on_remap_toggle=self.on_remap_toggle
        )
        self.widget.set_position(10, 20)

    def tearDown(self):
        pygame.quit()

    def test_initialization(self):
        self.assertEqual(self.widget.control_name, "throttle_up")
        self.assertEqual(self.widget.key_code, pygame.K_w)
        self.assertEqual(self.widget.label_rect.center[0], 10 + self.widget.label_rect.width // 2)
        self.assertEqual(self.widget.label_rect.centery, 20 + max(self.widget.label_rect.height, 30) // 2)

    def test_click_remap_starts_remapping(self):
        pos = self.widget.remap_button.rect.center
        self.widget.handle_event(pygame.event.Event(pygame.MOUSEMOTION, {'pos': pos}))
        self.widget.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': pos, 'button': 1}))
        self.widget.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': pos, 'button': 1}))

        self.assertTrue(self.widget.waiting_for_key)
        self.assertIsNone(self.widget.key_code)
        self.on_remap_toggle.assert_called_once_with(True)

    def test_key_assignment_after_remap(self):
        # Start remapping first
        self.widget._on_remap_click()

        event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_a})
        self.widget.handle_event(event)

        self.assertEqual(self.widget.key_code, pygame.K_a)
        self.assertFalse(self.widget.waiting_for_key)
        self.on_key_change.assert_called_once_with(pygame.K_a)
        self.on_remap_toggle.assert_called_with(False)

    def test_draw_does_not_crash(self):
        surface = pygame.Surface((300, 100))
        try:
            self.widget.draw(surface)
        except Exception as e:
            self.fail(f"Draw should not raise exception: {e}")


if __name__ == "__main__":
    unittest.main()
