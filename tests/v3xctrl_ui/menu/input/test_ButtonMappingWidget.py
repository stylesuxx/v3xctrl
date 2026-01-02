# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock

import pygame
import pygame.freetype

from v3xctrl_ui.menu.input import ButtonMappingWidget


class TestButtonMappingWidget(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.font = pygame.freetype.SysFont("freesansbold", 20)
        self.on_button_change = MagicMock()
        self.on_remap_toggle = MagicMock()

        self.widget = ButtonMappingWidget(
            control_name="trim_increase",
            button_number=3,
            font=self.font,
            on_button_change=self.on_button_change,
            on_remap_toggle=self.on_remap_toggle
        )
        self.widget.set_position(10, 20)

    def test_initialization_with_button(self):
        self.assertEqual(self.widget.control_name, "trim_increase")
        self.assertEqual(self.widget.button_number, 3)
        # Label rect is positioned and then centered vertically
        bar_center_y = 20 + self.widget.BAR_HEIGHT // 2
        self.assertEqual(self.widget.label_rect.centery, bar_center_y)
        self.assertFalse(self.widget.reset_button.disabled)

    def test_initialization_without_button(self):
        widget = ButtonMappingWidget(
            control_name="trim_decrease",
            button_number=None,
            font=self.font,
            on_button_change=self.on_button_change,
            on_remap_toggle=self.on_remap_toggle
        )
        widget.set_position(10, 20)

        self.assertEqual(widget.control_name, "trim_decrease")
        self.assertIsNone(widget.button_number)
        self.assertTrue(widget.reset_button.disabled)

    def test_click_assign_starts_remapping(self):
        pos = self.widget.remap_button.rect.center
        self.widget.handle_event(pygame.event.Event(pygame.MOUSEMOTION, {'pos': pos}))
        self.widget.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': pos,
            'button': 1
        }))
        self.widget.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'pos': pos,
            'button': 1
        }))

        self.assertTrue(self.widget.waiting_for_button)
        self.assertIsNone(self.widget.button_number)
        self.on_remap_toggle.assert_called_once_with(True)

    def test_button_assignment_after_remap(self):
        self.widget._on_remap_click()

        event = pygame.event.Event(pygame.JOYBUTTONDOWN, {'button': 5})
        result = self.widget.handle_event(event)

        self.assertTrue(result)
        self.assertEqual(self.widget.button_number, 5)
        self.assertFalse(self.widget.waiting_for_button)
        self.on_button_change.assert_called_once_with(5)
        self.assertEqual(self.on_remap_toggle.call_count, 2)
        self.on_remap_toggle.assert_called_with(False)
        self.assertFalse(self.widget.reset_button.disabled)

    def test_reset_clears_mapping(self):
        self.widget._on_reset_click()

        self.assertIsNone(self.widget.button_number)
        self.on_button_change.assert_called_once_with(None)
        self.assertTrue(self.widget.reset_button.disabled)

    def test_draw_does_not_crash(self):
        surface = pygame.Surface((600, 100))
        try:
            self.widget.draw(surface)
        except Exception as e:
            self.fail(f"Draw should not raise exception: {e}")

    def test_draw_waiting_state(self):
        self.widget.waiting_for_button = True
        surface = pygame.Surface((600, 100))
        try:
            self.widget.draw(surface)
        except Exception as e:
            self.fail(f"Draw should not raise exception in waiting state: {e}")

    def test_draw_no_button_state(self):
        self.widget.button_number = None
        surface = pygame.Surface((600, 100))
        try:
            self.widget.draw(surface)
        except Exception as e:
            self.fail(f"Draw should not raise exception with no button: {e}")

    def test_get_size_returns_correct_tuple(self):
        width, height = self.widget.get_size()
        self.assertIsInstance(width, int)
        self.assertIsInstance(height, int)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

    def test_enable_calls_button_enable(self):
        self.widget.remap_button.disable()
        self.widget.reset_button.disable()
        self.assertTrue(self.widget.remap_button.disabled)

        self.widget.enable()

        self.assertFalse(self.widget.remap_button.disabled)
        self.assertFalse(self.widget.reset_button.disabled)

    def test_enable_does_not_enable_reset_when_no_button(self):
        self.widget.button_number = None
        self.widget.remap_button.disable()
        self.widget.reset_button.disable()

        self.widget.enable()

        self.assertFalse(self.widget.remap_button.disabled)
        self.assertTrue(self.widget.reset_button.disabled)

    def test_disable_calls_button_disable(self):
        self.widget.remap_button.enable()
        self.widget.reset_button.enable()
        self.assertFalse(self.widget.remap_button.disabled)

        self.widget.disable()

        self.assertTrue(self.widget.remap_button.disabled)
        self.assertTrue(self.widget.reset_button.disabled)

    def test_button_positioning(self):
        self.widget.set_position(100, 50)

        bar_center_y = 50 + self.widget.BAR_HEIGHT // 2
        button_height = self.widget.remap_button.get_size()[1]
        expected_button_y = bar_center_y - button_height // 2

        self.assertEqual(self.widget.remap_button.rect.y, expected_button_y)
        self.assertEqual(self.widget.reset_button.rect.y, expected_button_y)

        expected_remap_x = 100 + self.widget.REMAP_BUTTON_OFFSET_X
        self.assertEqual(self.widget.remap_button.rect.x, expected_remap_x)

        expected_reset_x = expected_remap_x + self.widget.remap_button.get_size()[0] + self.widget.PADDING
        self.assertEqual(self.widget.reset_button.rect.x, expected_reset_x)


if __name__ == "__main__":
    unittest.main()
