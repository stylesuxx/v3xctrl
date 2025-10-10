import unittest
from unittest.mock import MagicMock, patch

import pygame

from src.v3xctrl_ui.menu.Menu import Menu


@patch("src.v3xctrl_ui.menu.Menu.pygame")
@patch("src.v3xctrl_ui.menu.Menu.Button")
class TestMenu(unittest.TestCase):
    def setUp(self):
        self.mock_gamepad_manager = MagicMock()
        self.mock_settings = MagicMock()
        self.mock_callback = MagicMock()
        self.mock_server = MagicMock()
        self.mock_callback_quit = MagicMock()

    def _setup_mocks(self, mock_button_class, mock_pygame):
        mock_surface = MagicMock()
        mock_pygame.Surface.return_value = mock_surface

        def create_mock_rect(*args, **kwargs):
            mock_rect = MagicMock()
            mock_rect.copy.return_value = mock_rect
            mock_rect.center = (50, 30)
            mock_rect.topleft = (0, 0)
            mock_rect.bottomleft = (0, 60)
            mock_rect.collidepoint.return_value = False

            return mock_rect

        mock_pygame.Rect.side_effect = create_mock_rect

        self.mock_button = MagicMock()
        mock_button_class.return_value = self.mock_button

        return mock_pygame, mock_button_class

    def test_initialization(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        self.assertEqual(menu.width, 800)
        self.assertEqual(menu.height, 600)
        self.assertEqual(menu.active_tab, "General")
        self.assertFalse(menu.disable_tabs)
        self.assertEqual(len(menu.tabs), 6)

        # New: Check tab bar caching is initialized
        self.assertTrue(menu.tab_bar_dirty)
        self.assertIsNotNone(menu.tab_bar_surface)
        self.assertIsNotNone(menu.background)

    def test_tab_creation(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        tab_names = [tab.name for tab in menu.tabs]
        expected_names = [
            "General",
            "Input",
            "OSD",
            "Network",
            "Streamer",
            "Frequencies",
        ]
        self.assertEqual(tab_names, expected_names)

    def test_get_active_tab(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class,mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        active_tab = menu._get_active_tab()
        self.assertIsNotNone(active_tab)
        self.assertEqual(active_tab.name, "General")

    def test_save_button_callback(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        mock_tab_view = MagicMock()
        mock_tab_view.get_settings.return_value = {"key1": "value1", "key2": "value2"}
        menu.tabs[0] = menu.tabs[0]._replace(view=mock_tab_view)

        menu._save_button_callback()

        mock_tab_view.get_settings.assert_called_once()
        self.mock_settings.set.assert_any_call("key1", "value1")
        self.mock_settings.set.assert_any_call("key2", "value2")
        self.mock_settings.save.assert_called_once()

    def test_exit_button_callback(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu.active_tab = "Input"
        menu._exit_button_callback()

        self.assertEqual(menu.active_tab, "General")
        self.mock_callback.assert_called_once()

    def test_quit_button_callback(self, mock_button_class, mock_pygame):
        mock_pygame, _ = self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu._quit_button_callback()
        self.mock_callback_quit.assert_called_once()

    def test_on_active_toggle_active(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu._on_active_toggle(True)

        self.assertTrue(menu.disable_tabs)
        self.mock_button.disable.assert_called()

    def test_on_active_toggle_inactive(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu._on_active_toggle(False)

        self.assertFalse(menu.disable_tabs)
        self.mock_button.enable.assert_called()

    def test_on_send_command_with_server(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        mock_command = MagicMock()
        mock_callback = MagicMock()

        menu._on_send_command(mock_command, mock_callback)

        self.mock_server.send_command.assert_called_once_with(mock_command, mock_callback)

    @patch("src.v3xctrl_ui.menu.Menu.logging")
    def test_on_send_command_without_server(self, mock_logging, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=None,
            callback_quit=self.mock_callback_quit
        )

        mock_command = MagicMock()
        mock_callback = MagicMock()

        menu._on_send_command(mock_command, mock_callback)

        mock_logging.error.assert_called_once()

    def test_handle_event_button_events(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        mock_event = MagicMock()
        menu.handle_event(mock_event)

        self.assertEqual(self.mock_button.handle_event.call_count, 3)

    def test_handle_event_tab_click_changes_active_tab(self, mock_button_class, mock_pygame):
        """Test that clicking a tab changes the active tab and marks tab bar as dirty"""
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        # Clear the initial dirty flag
        menu.tab_bar_dirty = False
        original_active = menu.active_tab

        mock_event = MagicMock()
        mock_event.type = mock_pygame.MOUSEBUTTONDOWN  # Use mocked pygame constant
        mock_event.button = 1
        mock_event.pos = (100, 30)

        # Make only the third tab respond to click
        for tab in menu.tabs:
            tab.rect.collidepoint.return_value = False
        menu.tabs[2].rect.collidepoint.return_value = True

        menu.handle_event(mock_event)

        # Active tab should change
        self.assertNotEqual(menu.active_tab, original_active)
        self.assertEqual(menu.active_tab, menu.tabs[2].name)

        # Tab bar should be marked dirty
        self.assertTrue(menu.tab_bar_dirty)

    def test_handle_event_tab_click_disabled(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu.disable_tabs = True
        original_active = menu.active_tab

        mock_event = MagicMock()
        mock_event.type = mock_pygame.MOUSEBUTTONDOWN  # Use mocked pygame constant
        mock_event.button = 1
        mock_event.pos = (100, 30)

        for tab in menu.tabs:
            tab.rect.collidepoint.return_value = False

        menu.tabs[3].rect.collidepoint.return_value = True
        menu.handle_event(mock_event)

        self.assertEqual(menu.active_tab, original_active)

    def test_render_tabs(self, mock_button_class, mock_pygame):
        """Test that _render_tabs renders to the cached tab_bar_surface"""
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu._render_tabs()

        # Should draw rectangles and lines to tab_bar_surface
        mock_pygame.draw.rect.assert_called()
        mock_pygame.draw.line.assert_called()

        # Should blit text to tab_bar_surface
        menu.tab_bar_surface.blit.assert_called()

    def test_draw_with_dirty_tab_bar(self, mock_button_class, mock_pygame):
        """Test that draw() re-renders tab bar when dirty"""
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        mock_surface = MagicMock()

        # Tab bar starts dirty
        self.assertTrue(menu.tab_bar_dirty)

        # Mock _render_tabs to track if it's called
        with patch.object(menu, '_render_tabs') as mock_render:
            menu.draw(mock_surface)
            mock_render.assert_called_once()

        # After drawing, tab bar should no longer be dirty
        self.assertFalse(menu.tab_bar_dirty)

    def test_draw_with_clean_tab_bar(self, mock_button_class, mock_pygame):
        """Test that draw() doesn't re-render tab bar when clean"""
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        mock_surface = MagicMock()

        # Mark tab bar as clean
        menu.tab_bar_dirty = False

        # Mock _render_tabs to track if it's called
        with patch.object(menu, '_render_tabs') as mock_render:
            menu.draw(mock_surface)
            mock_render.assert_not_called()

    def test_draw_blits_surfaces(self, mock_button_class, mock_pygame):
        """Test that draw() blits background and tab bar"""
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        mock_surface = MagicMock()
        menu.tab_bar_dirty = False  # Don't trigger re-render

        menu.draw(mock_surface)

        # Should blit background and tab_bar_surface
        self.assertGreaterEqual(mock_surface.blit.call_count, 2)

    def test_draw_buttons_called(self, mock_button_class, mock_pygame):
        """Test that _draw_buttons is called during draw()"""
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        mock_surface = MagicMock()
        menu.tab_bar_dirty = False

        with patch.object(menu, '_draw_buttons') as mock_draw_buttons:
            menu.draw(mock_surface)
            mock_draw_buttons.assert_called_once_with(mock_surface)

    def test_draw_buttons(self, mock_button_class, mock_pygame):
        """Test that _draw_buttons draws all three buttons"""
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        mock_surface = MagicMock()
        menu._draw_buttons(mock_surface)

        # All three buttons should be drawn
        self.assertEqual(self.mock_button.draw.call_count, 3)

    def test_get_active_tab_not_found(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class,mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu.active_tab = "NonExistentTab"
        self.assertIsNone(menu._get_active_tab())

    def test_save_button_callback_no_active_tab(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu.active_tab = "NonExistentTab"
        menu._save_button_callback()

        self.mock_settings.set.assert_not_called()
        self.mock_settings.save.assert_not_called()

    def test_handle_event_no_active_tab(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu.active_tab = "NonExistentTab"
        mock_event = MagicMock()
        menu.handle_event(mock_event)

    def test_draw_no_active_tab(self, mock_button_class, mock_pygame):
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        menu.active_tab = "NonExistentTab"
        mock_surface = MagicMock()
        menu.draw(mock_surface)

        mock_surface.blit.assert_called()
        self.assertEqual(self.mock_button.draw.call_count, 3)

    def test_tab_bar_dirty_flag_lifecycle(self, mock_button_class, mock_pygame):
        """Test the lifecycle of the tab_bar_dirty flag"""
        self._setup_mocks(mock_button_class, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server,
            callback_quit=self.mock_callback_quit
        )

        # Starts dirty
        self.assertTrue(menu.tab_bar_dirty)

        # Draw clears it
        mock_surface = MagicMock()
        menu.draw(mock_surface)
        self.assertFalse(menu.tab_bar_dirty)

        # Clicking a tab makes it dirty again
        mock_event = MagicMock()
        mock_event.type = mock_pygame.MOUSEBUTTONDOWN  # Use mocked pygame constant
        mock_event.button = 1
        mock_event.pos = (100, 30)

        menu.tabs[1].rect.collidepoint.return_value = True
        menu.handle_event(mock_event)
        self.assertTrue(menu.tab_bar_dirty)


if __name__ == "__main__":
    unittest.main()
