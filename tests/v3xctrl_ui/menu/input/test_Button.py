# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame
import pygame.freetype

from v3xctrl_ui.menu.input import Button


class TestButton(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.font.init()
        pygame.freetype.init()
        self.screen = pygame.Surface((300, 200))
        self.font = pygame.freetype.SysFont("freesansbold", 30)
        self.callback = MagicMock()
        self.button = Button("Test", self.font, self.callback, 100, 40)
        self.button.set_position(50, 50)

    def test_initialization(self):
        self.assertEqual(self.button.label, "Test")
        self.assertEqual(self.button.rect.width, 100)
        self.assertEqual(self.button.rect.height, 40)
        self.assertEqual(self.button.font, self.font)
        self.assertEqual(self.button.callback, self.callback)

        self.assertFalse(self.button.hovered)
        self.assertFalse(self.button.focused)
        self.assertFalse(self.button.disabled)

        self.assertTrue(self.button.visible)
        self.assertEqual(self.button.position, (50, 50))

    def test_cached_surfaces_created(self):
        """Test that all button states are pre-rendered and cached"""
        expected_states = {'normal', 'hover', 'active', 'disabled'}
        self.assertEqual(set(self.button.cached_surfaces.keys()), expected_states)

        for state, surface in self.button.cached_surfaces.items():
            self.assertIsInstance(surface, pygame.Surface)
            self.assertEqual(surface.get_size(), (100, 40))

    def test_initial_state(self):
        """Test that button starts in normal state"""
        self.assertEqual(self.button._current_state, 'normal')

    def test_hover_state_true(self):
        event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (75, 70)})
        self.assertTrue(self.button.handle_event(event))
        self.assertTrue(self.button.hovered)
        self.assertEqual(self.button._current_state, 'hover')

    def test_hover_state_false(self):
        event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (10, 10)})
        self.assertFalse(self.button.handle_event(event))
        self.assertFalse(self.button.hovered)
        self.assertEqual(self.button._current_state, 'normal')

    def test_focused_on_click_inside(self):
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 1
        })
        self.assertTrue(self.button.handle_event(event))
        self.assertTrue(self.button.focused)
        self.assertEqual(self.button._current_state, 'active')

    def test_no_focused_on_click_outside(self):
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (10, 10),
            'button': 1
        })
        self.assertFalse(self.button.handle_event(event))
        self.assertFalse(self.button.focused)

    def test_callback_on_release_inside(self):
        position = {
            'pos': (75, 70),
            'button': 1
        }
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, position)
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, position)

        self.assertTrue(self.button.handle_event(down_event))
        self.assertTrue(self.button.handle_event(up_event))

        self.callback.assert_called_once()
        self.assertFalse(self.button.focused)

    def test_no_callback_on_release_outside(self):
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 1
        })
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'pos': (10, 10),
            'button': 1
        })

        self.assertTrue(self.button.handle_event(down_event))
        self.assertTrue(self.button.handle_event(up_event))

        self.callback.assert_not_called()
        self.assertFalse(self.button.focused)

    def test_no_callback_on_release_when_not_focused(self):
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'pos': (75, 70),
            'button': 1
        })
        self.assertFalse(self.button.handle_event(up_event))

        self.callback.assert_not_called()
        self.assertFalse(self.button.focused)

    def test_right_click_ignored(self):
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 3
        })
        self.assertFalse(self.button.handle_event(down_event))

        self.assertFalse(self.button.focused)

    def test_disabled_button_ignores_events(self):
        self.button.disable()

        motion_event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (75, 70)})
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 1
        })
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'pos': (75, 70),
            'button': 1
        })

        self.assertFalse(self.button.handle_event(motion_event))
        self.assertFalse(self.button.handle_event(down_event))
        self.assertFalse(self.button.handle_event(up_event))

        self.assertFalse(self.button.hovered)
        self.assertFalse(self.button.focused)
        self.callback.assert_not_called()

    def test_enable_disable_toggle(self):
        self.assertFalse(self.button.disabled)

        self.button.disable()
        self.assertTrue(self.button.disabled)

        self.button.enable()
        self.assertFalse(self.button.disabled)

    def test_label_rendering_on_disable_enable(self):
        with patch.object(self.button, '_render_label') as mock_render:
            self.button.disable()
            mock_render.assert_called_with(Button.FONT_COLOR_DISABLED)

            self.button.enable()
            mock_render.assert_called_with(Button.FONT_COLOR)

    def test_disable_updates_state(self):
        """Test that disable() updates the visual state to 'disabled'"""
        self.assertEqual(self.button._current_state, 'normal')

        self.button.disable()
        self.assertEqual(self.button._current_state, 'disabled')
        self.assertTrue(self.button.disabled)

    def test_enable_updates_state(self):
        """Test that enable() updates the visual state from 'disabled'"""
        self.button.disable()
        self.assertEqual(self.button._current_state, 'disabled')

        self.button.enable()
        self.assertEqual(self.button._current_state, 'normal')
        self.assertFalse(self.button.disabled)

    def test_other_event_types_ignored(self):
        event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_SPACE})
        self.assertFalse(self.button.handle_event(event))

    def test_draw_does_not_crash(self):
        try:
            self.button.draw(self.screen)
        except Exception as e:
            self.fail(f"Button.draw() raised an exception: {e}")

    def test_private_draw_does_not_crash(self):
        try:
            self.button._draw(self.screen)
        except Exception as e:
            self.fail(f"Button._draw() raised an exception: {e}")

    def test_get_size(self):
        self.assertEqual(self.button.get_size(), (100, 40))
        self.assertEqual(self.button.width, 100)
        self.assertEqual(self.button.height, 40)

    def test_set_position(self):
        self.button.set_position(100, 200)

        self.assertEqual(self.button.rect.topleft, (100, 200))
        self.assertEqual(self.button.position, (100, 200))

        expected_center = self.button.rect.center
        self.assertEqual(self.button.label_rect.center, expected_center)

    def test_update_label_position(self):
        original_center = self.button.label_rect.center

        self.button.set_position(200, 300)

        new_center = self.button.label_rect.center
        self.assertNotEqual(original_center, new_center)
        self.assertEqual(new_center, self.button.rect.center)

    def test_draw_states(self):
        """Test that drawing works in all states"""
        surface = pygame.Surface((200, 100))

        test_states = [
            (False, False, False, 'normal'),
            (True, False, False, 'hover'),
            (True, True, False, 'active'),
            (False, False, True, 'disabled'),
        ]

        for hovered, focused, disabled, expected_state in test_states:
            with self.subTest(hovered=hovered, focused=focused, disabled=disabled):
                self.button.hovered = hovered
                self.button.focused = focused
                self.button.disabled = disabled
                self.button._update_state()

                self.assertEqual(self.button._current_state, expected_state)

                try:
                    self.button._draw(surface)
                except Exception as e:
                    self.fail(f"Button._draw() failed in state {expected_state}: {e}")

    def test_update_state_logic(self):
        """Test that _update_state correctly determines the current state"""
        # Normal state
        self.button.hovered = False
        self.button.focused = False
        self.button.disabled = False
        self.button._update_state()
        self.assertEqual(self.button._current_state, 'normal')

        # Hover state
        self.button.hovered = True
        self.button.focused = False
        self.button.disabled = False
        self.button._update_state()
        self.assertEqual(self.button._current_state, 'hover')

        # Active state (takes precedence over hover)
        self.button.hovered = True
        self.button.focused = True
        self.button.disabled = False
        self.button._update_state()
        self.assertEqual(self.button._current_state, 'active')

        # Disabled state (takes precedence over everything)
        self.button.hovered = True
        self.button.focused = True
        self.button.disabled = True
        self.button._update_state()
        self.assertEqual(self.button._current_state, 'disabled')

    def test_draw_uses_cached_surface(self):
        """Test that _draw uses the cached surface for current state"""
        surface = pygame.Surface((200, 100))

        # Verify that the correct cached surface exists for each state
        # and that drawing completes without error
        for state in ['normal', 'hover', 'active', 'disabled']:
            with self.subTest(state=state):
                self.button._current_state = state

                # Verify the cached surface exists
                self.assertIn(state, self.button.cached_surfaces)
                cached_surface = self.button.cached_surfaces[state]
                self.assertIsInstance(cached_surface, pygame.Surface)

                # Verify drawing works without error
                try:
                    self.button._draw(surface)
                except Exception as e:
                    self.fail(f"Button._draw() failed for state '{state}': {e}")

    def test_basewidget_inheritance(self):
        surface = pygame.Surface((200, 100))

        self.button.visible = True
        with patch.object(self.button, '_draw') as mock_private_draw:
            self.button.draw(surface)
            mock_private_draw.assert_called_once_with(surface)

        self.button.visible = False
        with patch.object(self.button, '_draw') as mock_private_draw:
            self.button.draw(surface)
            mock_private_draw.assert_not_called()

    def test_width_height_properties(self):
        self.assertEqual(self.button.width, 100)
        self.assertEqual(self.button.height, 40)

        button2 = Button("Test2", self.font, self.callback, 150)
        self.assertEqual(button2.width, 150)
        self.assertEqual(button2.height, 54)

    def test_mouse_drag_behavior(self):
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 1
        })
        self.assertTrue(self.button.handle_event(down_event))
        self.assertTrue(self.button.focused)

        motion_event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (10, 10)})
        self.assertFalse(self.button.handle_event(motion_event))
        self.assertFalse(self.button.hovered)
        self.assertTrue(self.button.focused)

        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'pos': (10, 10),
            'button': 1
        })
        self.assertTrue(self.button.handle_event(up_event))
        self.assertFalse(self.button.focused)
        self.callback.assert_not_called()

    def test_multiple_mouse_downs(self):
        down_event1 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 1
        })
        self.assertTrue(self.button.handle_event(down_event1))
        self.assertTrue(self.button.focused)

        down_event2 = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 1
        })
        self.assertTrue(self.button.handle_event(down_event2))
        self.assertTrue(self.button.focused)

    def test_hover_while_focused(self):
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 1
        })
        self.button.handle_event(down_event)
        self.assertTrue(self.button.focused)

        motion_event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (10, 10)})
        self.assertFalse(self.button.handle_event(motion_event))
        self.assertFalse(self.button.hovered)
        self.assertTrue(self.button.focused)

        motion_event2 = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (75, 70)})
        self.assertTrue(self.button.handle_event(motion_event2))
        self.assertTrue(self.button.hovered)
        self.assertTrue(self.button.focused)

    def test_label_rect_positioning(self):
        self.assertEqual(self.button.label_rect.center, self.button.rect.center)

        self.button.set_position(200, 300)
        self.assertEqual(self.button.label_rect.center, self.button.rect.center)

    def test_callback_only_called_once_per_click(self):
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 1
        })
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'pos': (75, 70),
            'button': 1
        })

        self.button.handle_event(down_event)
        self.button.handle_event(up_event)
        self.assertEqual(self.callback.call_count, 1)

        up_event2 = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'pos': (75, 70),
            'button': 1
        })
        self.button.handle_event(up_event2)
        self.assertEqual(self.callback.call_count, 1)

    def test_state_transitions(self):
        """Test state transitions happen correctly during user interactions"""
        # Start in normal state
        self.assertEqual(self.button._current_state, 'normal')

        # Mouse enters -> hover state
        hover_event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (75, 70)})
        self.button.handle_event(hover_event)
        self.assertEqual(self.button._current_state, 'hover')

        # Mouse clicks -> active state
        down_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
            'pos': (75, 70),
            'button': 1
        })
        self.button.handle_event(down_event)
        self.assertEqual(self.button._current_state, 'active')

        # Mouse releases -> back to hover (since mouse is still over button)
        up_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {
            'pos': (75, 70),
            'button': 1
        })
        self.button.handle_event(up_event)
        self.assertEqual(self.button._current_state, 'hover')

        # Mouse leaves -> normal state
        leave_event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': (10, 10)})
        self.button.handle_event(leave_event)
        self.assertEqual(self.button._current_state, 'normal')


if __name__ == "__main__":
    unittest.main()
