# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame
from pygame.freetype import SysFont

from v3xctrl_ui.menu.input import Checkbox


class TestCheckbox(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.freetype.init()
        self.screen = pygame.display.set_mode((300, 200))
        self.font = SysFont("freesansbold", 20)
        self.change_called_with = []

    def on_change(self, value):
        self.change_called_with.append(value)

    def test_initialization(self):
        checkbox = Checkbox("Test", font=self.font, checked=True, on_change=self.on_change)

        self.assertEqual(checkbox.label, "Test")
        self.assertTrue(checkbox.checked)
        self.assertEqual(checkbox.font, self.font)
        self.assertEqual(checkbox.on_change, self.on_change)

        self.assertIsNotNone(checkbox.box_rect)
        self.assertEqual(checkbox.box_rect.width, Checkbox.BOX_SIZE)
        self.assertEqual(checkbox.box_rect.height, Checkbox.BOX_SIZE)

        self.assertTrue(checkbox.visible)
        self.assertEqual(checkbox.x, 0)
        self.assertEqual(checkbox.y, 0)

    def test_initialization_unchecked(self):
        checkbox = Checkbox("Unchecked", font=self.font, checked=False, on_change=self.on_change)
        self.assertFalse(checkbox.checked)

    def test_cached_surfaces_created(self):
        """Test that both checkbox states are pre-rendered and cached"""
        checkbox = Checkbox("Test", font=self.font, checked=False, on_change=self.on_change)

        expected_states = {'checked', 'unchecked'}
        self.assertEqual(set(checkbox.cached_surfaces.keys()), expected_states)

        for state, surface in checkbox.cached_surfaces.items():
            self.assertIsInstance(surface, pygame.Surface)
            # Verify surface size matches get_size()
            expected_width, expected_height = checkbox.get_size()
            self.assertEqual(surface.get_size(), (expected_width, expected_height))

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

    def test_click_on_label_area_toggles_state(self):
        """Test clicking in the label area (right side) toggles state"""
        checkbox = Checkbox("ClickLabel", font=self.font, checked=False, on_change=self.on_change)

        # Click in the label area (to the right of the box)
        label_x = checkbox.x + Checkbox.BOX_SIZE + Checkbox.BOX_MARGIN + 5
        label_y = checkbox.y + 10

        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (label_x, label_y),
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

    def test_set_position_updates_basewidget_coords(self):
        checkbox = Checkbox("Position", font=self.font, checked=False, on_change=self.on_change)
        checkbox.set_position(100, 150)

        self.assertEqual(checkbox.position, (100, 150))

    def test_get_size(self):
        checkbox = Checkbox("SizeTest", font=self.font, checked=False, on_change=self.on_change)

        expected_width = checkbox.BOX_SIZE + checkbox.BOX_MARGIN + checkbox.label_width
        expected_height = max(checkbox.BOX_SIZE, checkbox.label_height)

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

    def test_click_detection_uses_full_area(self):
        """Test that clicking anywhere in the checkbox area works"""
        checkbox = Checkbox("FullArea", font=self.font, checked=False, on_change=self.on_change)
        checkbox.set_position(50, 50)

        width, height = checkbox.get_size()

        # Test clicks at different positions within the checkbox area
        test_positions = [
            (50, 50),  # top-left
            (50 + width - 1, 50),  # top-right
            (50, 50 + height - 1),  # bottom-left
            (50 + width // 2, 50 + height // 2),  # center
        ]

        for pos in test_positions:
            with self.subTest(pos=pos):
                checkbox.checked = False
                self.change_called_with.clear()

                event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
                    'pos': pos,
                    'button': 1
                })
                self.assertTrue(checkbox.handle_event(event))
                self.assertTrue(checkbox.checked)
                self.assertEqual(self.change_called_with, [True])

    def test_click_just_outside_boundary(self):
        """Test that clicks just outside the checkbox area don't toggle"""
        checkbox = Checkbox("Boundary", font=self.font, checked=False, on_change=self.on_change)
        checkbox.set_position(50, 50)

        width, height = checkbox.get_size()

        # Test clicks just outside the boundaries
        test_positions = [
            (49, 50),  # left of area
            (50 + width, 50),  # right of area
            (50, 49),  # above area
            (50, 50 + height),  # below area
        ]

        for pos in test_positions:
            with self.subTest(pos=pos):
                checkbox.checked = False
                self.change_called_with.clear()

                event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
                    'pos': pos,
                    'button': 1
                })
                self.assertFalse(checkbox.handle_event(event))
                self.assertFalse(checkbox.checked)
                self.assertEqual(self.change_called_with, [])

    def test_draw_uses_correct_cached_surface(self):
        """Test that _draw uses the correct cached surface based on checked state"""
        checkbox = Checkbox("DrawState", font=self.font, checked=False, on_change=self.on_change)
        surface = pygame.Surface((200, 100))

        # Test unchecked state
        checkbox.checked = False
        self.assertIn('unchecked', checkbox.cached_surfaces)
        try:
            checkbox._draw(surface)
        except Exception as e:
            self.fail(f"_draw() failed in unchecked state: {e}")

        # Test checked state
        checkbox.checked = True
        self.assertIn('checked', checkbox.cached_surfaces)
        try:
            checkbox._draw(surface)
        except Exception as e:
            self.fail(f"_draw() failed in checked state: {e}")

    def test_label_dimensions_stored(self):
        """Test that label width and height are stored during initialization"""
        checkbox = Checkbox("TestLabel", font=self.font, checked=False, on_change=self.on_change)

        self.assertIsInstance(checkbox.label_width, int)
        self.assertIsInstance(checkbox.label_height, int)
        self.assertGreater(checkbox.label_width, 0)
        self.assertGreater(checkbox.label_height, 0)

    def test_disabled_checkbox_ignores_clicks(self):
        """Test that disabled checkbox doesn't respond to clicks"""
        checkbox = Checkbox("Disabled", font=self.font, checked=False, on_change=self.on_change)
        checkbox.disabled = True

        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': checkbox.box_rect.center,
            'button': 1
        })

        self.assertFalse(checkbox.handle_event(event))
        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [])

    def test_position_after_creation(self):
        """Test that checkbox can be positioned after creation and clicks still work"""
        checkbox = Checkbox("Movable", font=self.font, checked=False, on_change=self.on_change)

        # Move to new position
        checkbox.set_position(100, 150)

        # Click at new position
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (100 + 10, 150 + 10),
            'button': 1
        })

        self.assertTrue(checkbox.handle_event(event))
        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [True])


if __name__ == '__main__':
    unittest.main()
