import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
from pygame.freetype import SysFont
from unittest.mock import MagicMock, patch
from v3xctrl_ui.menu.input import Checkbox


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

        # Test basic properties
        self.assertEqual(checkbox.label, "Test")
        self.assertTrue(checkbox.checked)
        self.assertEqual(checkbox.font, self.font)
        self.assertEqual(checkbox.on_change, self.on_change)

        # Test rect initialization
        self.assertIsNotNone(checkbox.box_rect)
        self.assertIsNotNone(checkbox.label_rect)
        self.assertEqual(checkbox.box_rect.width, Checkbox.BOX_SIZE)
        self.assertEqual(checkbox.box_rect.height, Checkbox.BOX_SIZE)

        # Test BaseWidget inheritance
        self.assertTrue(checkbox.visible)  # Inherited from BaseWidget
        self.assertEqual(checkbox.x, 0)
        self.assertEqual(checkbox.y, 0)

    def test_constants(self):
        """Test class constants"""
        self.assertEqual(Checkbox.BOX_SIZE, 25)
        self.assertEqual(Checkbox.BOX_MARGIN, 10)
        # Color constants would be tested here if we had access to the color values

    def test_initialization_unchecked(self):
        """Test initialization with unchecked state"""
        checkbox = Checkbox("Unchecked", font=self.font, checked=False, on_change=self.on_change)
        self.assertFalse(checkbox.checked)

    def test_draw_does_not_crash(self):
        checkbox = Checkbox("DrawTest", font=self.font, checked=False, on_change=self.on_change)
        try:
            checkbox.draw(self.screen)
        except Exception as e:
            self.fail(f"draw() raised an exception: {e}")

    def test_private_draw_does_not_crash(self):
        """Test that _draw method works"""
        checkbox = Checkbox("DrawTest", font=self.font, checked=False, on_change=self.on_change)
        try:
            checkbox._draw(self.screen)
        except Exception as e:
            self.fail(f"_draw() raised an exception: {e}")

    def test_click_on_box_toggles_state(self):
        checkbox = Checkbox("ClickBox", font=self.font, checked=False, on_change=self.on_change)
        center = checkbox.box_rect.center
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': center, 'button': 1})

        result = checkbox.handle_event(event)

        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [True])
        self.assertTrue(result)  # Should return True when event is handled

    def test_click_on_label_toggles_state(self):
        checkbox = Checkbox("ClickLabel", font=self.font, checked=False, on_change=self.on_change)
        center = checkbox.label_rect.center
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': center, 'button': 1})

        result = checkbox.handle_event(event)

        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [True])
        self.assertTrue(result)

    def test_click_outside_does_not_toggle(self):
        checkbox = Checkbox("OutsideClick", font=self.font, checked=False, on_change=self.on_change)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (300, 300), 'button': 1})

        result = checkbox.handle_event(event)

        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [])
        self.assertFalse(result)

    def test_right_click_ignored(self):
        """Test that right clicks don't toggle checkbox"""
        checkbox = Checkbox("RightClick", font=self.font, checked=False, on_change=self.on_change)
        center = checkbox.box_rect.center
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': center, 'button': 3})

        result = checkbox.handle_event(event)

        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [])
        self.assertFalse(result)  # Should return False for non-left clicks

    def test_other_events_ignored(self):
        """Test that other event types are ignored"""
        checkbox = Checkbox("OtherEvents", font=self.font, checked=False, on_change=self.on_change)
        keydown_event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_SPACE})

        result = checkbox.handle_event(keydown_event)

        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [])
        self.assertFalse(result)

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

        # Test BaseWidget position tracking (should be overridden to NOT call super())
        self.assertEqual(checkbox.x, 50)
        self.assertEqual(checkbox.y, 80)

        # Test checkbox-specific positioning
        self.assertEqual(checkbox.box_rect.topleft, (50, 80))
        expected_label_x = 50 + checkbox.BOX_SIZE + checkbox.BOX_MARGIN
        self.assertEqual(checkbox.label_rect.x, expected_label_x)

        # Label should be vertically centered with box
        self.assertEqual(checkbox.label_rect.centery, checkbox.box_rect.centery)

    def test_set_position_updates_basewidget_coords(self):
        """Test that set_position properly updates BaseWidget coordinates"""
        checkbox = Checkbox("Position", font=self.font, checked=False, on_change=self.on_change)
        checkbox.set_position(100, 150)

        # Since set_position sets x, y directly (not calling super),
        # the position property should reflect the new values
        self.assertEqual(checkbox.position, (100, 150))

    def test_get_size(self):
        checkbox = Checkbox("SizeTest", font=self.font, checked=False, on_change=self.on_change)
        width, height = checkbox.get_size()

        expected_width = checkbox.BOX_SIZE + checkbox.BOX_MARGIN + checkbox.label_rect.width
        expected_height = max(checkbox.BOX_SIZE, checkbox.label_rect.height)

        self.assertEqual(width, expected_width)
        self.assertEqual(height, expected_height)

    def test_set_checked_method(self):
        """Test the set_checked method"""
        checkbox = Checkbox("SetChecked", font=self.font, checked=False, on_change=self.on_change)

        # Test setting to True
        checkbox.set_checked(True)
        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [True])

        # Reset callback tracking
        self.change_called_with.clear()

        # Test setting to same value (should not trigger callback)
        checkbox.set_checked(True)
        self.assertTrue(checkbox.checked)
        self.assertEqual(self.change_called_with, [])  # No callback called

        # Test setting to False
        checkbox.set_checked(False)
        self.assertFalse(checkbox.checked)
        self.assertEqual(self.change_called_with, [False])

    def test_draw_checked_and_unchecked(self):
        checkbox = Checkbox("DrawTest", font=self.font, checked=False, on_change=self.on_change)

        # Test unchecked draw
        try:
            checkbox.draw(self.screen)
        except Exception as e:
            self.fail(f"draw() raised exception when unchecked: {e}")

        # Test checked draw (draws the check circle)
        checkbox.checked = True
        try:
            checkbox.draw(self.screen)
        except Exception as e:
            self.fail(f"draw() raised exception when checked: {e}")

    @patch('pygame.draw.rect')
    @patch('pygame.gfxdraw.filled_circle')
    @patch('pygame.gfxdraw.aacircle')
    def test_draw_calls_correct_methods(self, mock_aacircle, mock_filled_circle, mock_draw_rect):
        """Test that drawing calls the correct pygame methods"""
        checkbox = Checkbox("DrawMethods", font=self.font, checked=True, on_change=self.on_change)
        surface = pygame.Surface((200, 100))

        checkbox._draw(surface)

        # Should draw rectangle for box background and border
        self.assertEqual(mock_draw_rect.call_count, 2)

        # Should draw filled circle and anti-aliased circle when checked
        mock_filled_circle.assert_called_once()
        mock_aacircle.assert_called_once()

    @patch('pygame.draw.rect')
    @patch('pygame.gfxdraw.filled_circle')
    def test_draw_unchecked_no_circle(self, mock_filled_circle, mock_draw_rect):
        """Test that unchecked checkbox doesn't draw circle"""
        checkbox = Checkbox("Unchecked", font=self.font, checked=False, on_change=self.on_change)
        surface = pygame.Surface((200, 100))

        checkbox._draw(surface)

        # Should draw rectangle for box
        mock_draw_rect.assert_called()

        # Should NOT draw circle when unchecked
        mock_filled_circle.assert_not_called()

    def test_basewidget_inheritance(self):
        """Test BaseWidget functionality"""
        checkbox = Checkbox("BaseWidget", font=self.font, checked=False, on_change=self.on_change)
        surface = pygame.Surface((200, 100))

        # Test visibility affects drawing
        checkbox.visible = True
        with patch.object(checkbox, '_draw') as mock_private_draw:
            checkbox.draw(surface)
            mock_private_draw.assert_called_once_with(surface)

        # When invisible, should not call _draw
        checkbox.visible = False
        with patch.object(checkbox, '_draw') as mock_private_draw:
            checkbox.draw(surface)
            mock_private_draw.assert_not_called()

    def test_width_height_properties(self):
        """Test width and height properties from BaseWidget"""
        checkbox = Checkbox("Properties", font=self.font, checked=False, on_change=self.on_change)
        expected_width, expected_height = checkbox.get_size()

        self.assertEqual(checkbox.width, expected_width)
        self.assertEqual(checkbox.height, expected_height)

    def test_callback_with_mock(self):
        """Test checkbox with mocked callback"""
        mock_callback = MagicMock()
        checkbox = Checkbox("MockCallback", font=self.font, checked=False, on_change=mock_callback)

        # Click to toggle
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': checkbox.box_rect.center, 'button': 1})
        checkbox.handle_event(event)

        mock_callback.assert_called_once_with(True)

        # Toggle again
        checkbox.handle_event(event)
        self.assertEqual(mock_callback.call_count, 2)
        mock_callback.assert_called_with(False)

    def test_label_positioning_after_move(self):
        """Test that label stays properly positioned after moving checkbox"""
        checkbox = Checkbox("LabelPos", font=self.font, checked=False, on_change=self.on_change)

        # Move checkbox
        checkbox.set_position(75, 125)

        # Label should be positioned relative to box
        expected_label_x = 75 + Checkbox.BOX_SIZE + Checkbox.BOX_MARGIN
        self.assertEqual(checkbox.label_rect.x, expected_label_x)

        # Label should be vertically centered with box
        self.assertEqual(checkbox.label_rect.centery, checkbox.box_rect.centery)


if __name__ == '__main__':
    unittest.main()
