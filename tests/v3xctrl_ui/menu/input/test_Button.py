import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
import pygame.freetype
import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_ui.menu.input import Button


class TestButton(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.font.init()
        pygame.freetype.init()
        self.screen = pygame.Surface((300, 200))
        self.font = pygame.freetype.SysFont("freesansbold", 30)
        self.callback = MagicMock()
        self.button = Button("Test", 100, 40, self.font, self.callback)
        self.button.set_position(50, 50)

    def tearDown(self):
        pygame.freetype.quit()
        pygame.font.quit()
        pygame.quit()

    def test_initialization(self):
        """Test button initialization"""
        self.assertEqual(self.button.label, "Test")
        self.assertEqual(self.button.rect.width, 100)
        self.assertEqual(self.button.rect.height, 40)
        self.assertEqual(self.button.font, self.font)
        self.assertEqual(self.button.callback, self.callback)

        # Test initial state
        self.assertFalse(self.button.hovered)
        self.assertFalse(self.button.focused)  # Changed from active to focused
        self.assertFalse(self.button.disabled)

        # Test BaseWidget inheritance
        self.assertTrue(self.button.visible)  # Inherited from BaseWidget
        self.assertEqual(self.button.position, (50, 50))

    def test_constants(self):
        """Test class constants"""
        self.assertEqual(Button.FONT_COLOR, (255, 255, 255))
        self.assertEqual(Button.FONT_COLOR_DISABLED, (180, 180, 180))
        self.assertEqual(Button.BG_COLOR, (100, 100, 100))
        self.assertEqual(Button.HOVER_COLOR, (120, 120, 120))
        self.assertEqual(Button.ACTIVE_COLOR, (70, 70, 70))
        self.assertEqual(Button.BG_COLOR_DISABLED, (60, 60, 60))
        self.assertEqual(Button.BORDER_COLOR, (180, 180, 180))
        self.assertEqual(Button.BORDER_WIDTH, 2)
        self.assertEqual(Button.BORDER_RADIUS, 8)

    def test_hover_state_true(self):
        """Test hovering over button"""
        event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (75, 70)})  # Inside button
        result = self.button.handle_event(event)
        self.assertTrue(self.button.hovered)
        self.assertTrue(result)  # Should return True when hovering

    def test_hover_state_false(self):
        """Test not hovering over button"""
        event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (10, 10)})  # Outside button
        result = self.button.handle_event(event)
        self.assertFalse(self.button.hovered)
        self.assertFalse(result)  # Should return False when not hovering

    def test_focused_on_click_inside(self):
        """Test clicking inside button sets focused state"""
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 1})
        result = self.button.handle_event(down_event)
        self.assertTrue(self.button.focused)  # Changed from active to focused
        self.assertTrue(result)

    def test_no_focused_on_click_outside(self):
        """Test that clicking outside doesn't focus button"""
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (10, 10), 'button': 1})
        result = self.button.handle_event(down_event)
        self.assertFalse(self.button.focused)  # Changed from active to focused
        self.assertFalse(result)  # Should return False for clicks outside

    def test_callback_on_release_inside(self):
        """Test callback fires on mouse up inside after mouse down inside"""
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 1})
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (75, 70), 'button': 1})

        result1 = self.button.handle_event(down_event)
        result2 = self.button.handle_event(up_event)

        self.callback.assert_called_once()
        self.assertFalse(self.button.focused)  # Should clear focus after release
        self.assertTrue(result1)
        self.assertTrue(result2)

    def test_no_callback_on_release_outside(self):
        """Test no callback when releasing outside after clicking inside"""
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 1})
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (10, 10), 'button': 1})

        result1 = self.button.handle_event(down_event)
        result2 = self.button.handle_event(up_event)

        self.callback.assert_not_called()
        self.assertFalse(self.button.focused)  # Should clear focus after release
        self.assertTrue(result1)  # Mouse down should return True
        self.assertTrue(result2)  # Mouse up should return True (was_focused)

    def test_no_callback_on_release_when_not_focused(self):
        """Test that release without prior activation doesn't trigger callback"""
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (75, 70), 'button': 1})
        result = self.button.handle_event(up_event)

        self.callback.assert_not_called()
        self.assertFalse(self.button.focused)
        self.assertFalse(result)  # Should return False (was_focused is False)

    def test_right_click_ignored(self):
        """Test that right clicks don't activate button"""
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 3})
        result = self.button.handle_event(down_event)

        self.assertFalse(self.button.focused)
        self.assertFalse(result)  # Right clicks should return False

    def test_disabled_button_ignores_events(self):
        """Test disabled button ignores all events"""
        self.button.disable()
        motion_event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (75, 70)})
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 1})
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (75, 70), 'button': 1})

        result1 = self.button.handle_event(motion_event)
        result2 = self.button.handle_event(down_event)
        result3 = self.button.handle_event(up_event)

        self.assertFalse(self.button.hovered)
        self.assertFalse(self.button.focused)
        self.callback.assert_not_called()

        # Disabled button should return False for all events
        self.assertFalse(result1)
        self.assertFalse(result2)
        self.assertFalse(result3)

    def test_enable_disable_toggle(self):
        """Test enable/disable functionality"""
        # Test initial state
        self.assertFalse(self.button.disabled)

        # Test disable
        self.button.disable()
        self.assertTrue(self.button.disabled)

        # Test enable
        self.button.enable()
        self.assertFalse(self.button.disabled)

    def test_label_rendering_on_disable_enable(self):
        """Test that label color changes when disabled/enabled"""
        # Mock the font render to track calls
        with patch.object(self.button, '_render_label') as mock_render:
            self.button.disable()
            mock_render.assert_called_with(Button.FONT_COLOR_DISABLED)

            self.button.enable()
            mock_render.assert_called_with(Button.FONT_COLOR)

    def test_other_event_types_ignored(self):
        """Test that other event types return False"""
        keydown_event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_SPACE})
        result = self.button.handle_event(keydown_event)
        self.assertFalse(result)

    def test_draw_does_not_crash(self):
        """Test that drawing doesn't crash"""
        try:
            self.button.draw(self.screen)
        except Exception as e:
            self.fail(f"Button.draw() raised an exception: {e}")

    def test_private_draw_does_not_crash(self):
        """Test that _draw method works"""
        try:
            self.button._draw(self.screen)
        except Exception as e:
            self.fail(f"Button._draw() raised an exception: {e}")

    def test_get_size(self):
        """Test get_size method"""
        width, height = self.button.get_size()
        self.assertEqual(width, self.button.rect.width)
        self.assertEqual(height, self.button.rect.height)
        self.assertEqual(width, 100)
        self.assertEqual(height, 40)

    def test_set_position(self):
        """Test position setting updates rect and label"""
        self.button.set_position(100, 200)

        self.assertEqual(self.button.rect.topleft, (100, 200))
        self.assertEqual(self.button.position, (100, 200))

        # Label should be centered in the button
        expected_center = self.button.rect.center
        self.assertEqual(self.button.label_rect.center, expected_center)

    def test_update_label_position(self):
        """Test label position update"""
        original_center = self.button.label_rect.center

        # Move button
        self.button.set_position(200, 300)

        # Label center should have moved with the button
        new_center = self.button.label_rect.center
        self.assertNotEqual(original_center, new_center)
        self.assertEqual(new_center, self.button.rect.center)

    def test_draw_states(self):
        """Test drawing in different states"""
        surface = pygame.Surface((200, 100))

        # Test all drawing states without crashing
        test_states = [
            # (hovered, focused, disabled)
            (False, False, False),  # Normal
            (True, False, False),   # Hovered
            (True, True, False),    # Focused (active)
            (False, False, True),   # Disabled
        ]

        for hovered, focused, disabled in test_states:
            with self.subTest(hovered=hovered, focused=focused, disabled=disabled):
                self.button.hovered = hovered
                self.button.focused = focused  # Changed from active to focused
                self.button.disabled = disabled

                try:
                    self.button._draw(surface)
                except Exception as e:
                    self.fail(f"Button._draw() failed in state (h={hovered}, f={focused}, d={disabled}): {e}")

    @patch('pygame.draw.rect')
    def test_draw_colors(self, mock_draw_rect):
        """Test that correct colors are used in different states"""
        surface = pygame.Surface((200, 100))

        # Test normal state
        self.button.hovered = False
        self.button.focused = False
        self.button.disabled = False
        self.button._draw(surface)

        # First call should be background with BG_COLOR
        first_call = mock_draw_rect.call_args_list[0]
        self.assertEqual(first_call[0][1], Button.BG_COLOR)

        mock_draw_rect.reset_mock()

        # Test hovered state
        self.button.hovered = True
        self.button.focused = False  # Need to ensure focused is False
        self.button._draw(surface)
        first_call = mock_draw_rect.call_args_list[0]
        self.assertEqual(first_call[0][1], Button.HOVER_COLOR)

        mock_draw_rect.reset_mock()

        # Test focused state (active) - this takes priority over hover
        self.button.hovered = False  # Reset hover state
        self.button.focused = True  # Changed from active to focused
        self.button._draw(surface)
        first_call = mock_draw_rect.call_args_list[0]
        self.assertEqual(first_call[0][1], Button.ACTIVE_COLOR)

        mock_draw_rect.reset_mock()

        # Test disabled state
        self.button.hovered = False
        self.button.focused = False
        self.button.disabled = True
        self.button._draw(surface)
        first_call = mock_draw_rect.call_args_list[0]
        self.assertEqual(first_call[0][1], Button.BG_COLOR_DISABLED)

    def test_basewidget_inheritance(self):
        """Test BaseWidget functionality"""
        # Test visibility affects drawing
        surface = pygame.Surface((200, 100))

        # When visible, should call _draw
        self.button.visible = True
        with patch.object(self.button, '_draw') as mock_private_draw:
            self.button.draw(surface)
            mock_private_draw.assert_called_once_with(surface)

        # When invisible, should not call _draw
        self.button.visible = False
        with patch.object(self.button, '_draw') as mock_private_draw:
            self.button.draw(surface)
            mock_private_draw.assert_not_called()

    def test_width_height_properties(self):
        """Test width and height properties from BaseWidget"""
        self.assertEqual(self.button.width, 100)
        self.assertEqual(self.button.height, 40)

        # Test with different size
        button2 = Button("Test2", 150, 60, self.font, self.callback)
        self.assertEqual(button2.width, 150)
        self.assertEqual(button2.height, 60)

    def test_mouse_drag_behavior(self):
        """Test mouse drag behavior (press inside, release outside)"""
        # Press inside
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 1})
        result1 = self.button.handle_event(down_event)
        self.assertTrue(self.button.focused)
        self.assertTrue(result1)

        # Move outside while pressed (this should not affect focus)
        motion_event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (10, 10)})
        result2 = self.button.handle_event(motion_event)
        self.assertFalse(self.button.hovered)  # Not hovering anymore
        self.assertTrue(self.button.focused)   # But still focused
        self.assertFalse(result2)  # Motion outside returns False

        # Release outside
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (10, 10), 'button': 1})
        result3 = self.button.handle_event(up_event)
        self.assertFalse(self.button.focused)  # Focus cleared
        self.callback.assert_not_called()      # No callback fired
        self.assertTrue(result3)               # But event was handled (was_focused)

    def test_multiple_mouse_downs(self):
        """Test multiple mouse down events"""
        # First click
        down_event1 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 1})
        result1 = self.button.handle_event(down_event1)
        self.assertTrue(self.button.focused)
        self.assertTrue(result1)

        # Second click while already focused
        down_event2 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 1})
        result2 = self.button.handle_event(down_event2)
        self.assertTrue(self.button.focused)  # Still focused
        self.assertTrue(result2)

    def test_hover_while_focused(self):
        """Test hover behavior while button is focused"""
        # Click to focus
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 1})
        self.button.handle_event(down_event)
        self.assertTrue(self.button.focused)

        # Move outside - should lose hover but keep focus
        motion_event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (10, 10)})
        result = self.button.handle_event(motion_event)
        self.assertFalse(self.button.hovered)
        self.assertTrue(self.button.focused)   # Focus maintained
        self.assertFalse(result)

        # Move back inside - should regain hover
        motion_event2 = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (75, 70)})
        result2 = self.button.handle_event(motion_event2)
        self.assertTrue(self.button.hovered)
        self.assertTrue(self.button.focused)
        self.assertTrue(result2)

    def test_label_rect_positioning(self):
        """Test that label rect is properly positioned"""
        # Initial position
        self.assertEqual(self.button.label_rect.center, self.button.rect.center)

        # After moving
        self.button.set_position(200, 300)
        self.assertEqual(self.button.label_rect.center, self.button.rect.center)

    def test_callback_only_called_once_per_click(self):
        """Test that callback is only called once per complete click cycle"""
        # Complete click cycle
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (75, 70), 'button': 1})
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (75, 70), 'button': 1})

        self.button.handle_event(down_event)
        self.button.handle_event(up_event)
        self.assertEqual(self.callback.call_count, 1)

        # Additional mouse up should not call callback again
        up_event2 = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (75, 70), 'button': 1})
        self.button.handle_event(up_event2)
        self.assertEqual(self.callback.call_count, 1)  # Still only 1 call


if __name__ == "__main__":
    unittest.main()
