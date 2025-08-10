import unittest
from unittest.mock import MagicMock, patch, Mock
import pygame

from src.v3xctrl_ui.menu.Menu import Menu


class TestMenu(unittest.TestCase):
    def setUp(self):
        # Mock pygame
        self.patcher_pygame = patch("src.v3xctrl_ui.menu.Menu.pygame")
        self.mock_pygame = self.patcher_pygame.start()

        # Mock pygame.Surface
        mock_surface = MagicMock()
        self.mock_pygame.Surface.return_value = mock_surface

        # Mock pygame.Rect - create separate instances for each call
        def create_mock_rect(*args, **kwargs):
            mock_rect = MagicMock()
            mock_rect.copy.return_value = mock_rect
            mock_rect.center = (50, 30)
            mock_rect.topleft = (0, 0)
            mock_rect.bottomleft = (0, 60)
            mock_rect.collidepoint.return_value = False
            return mock_rect

        self.mock_pygame.Rect.side_effect = create_mock_rect

        # Mock the tab classes
        self.patcher_general_tab = patch("src.v3xctrl_ui.menu.Menu.GeneralTab")
        self.patcher_osd_tab = patch("src.v3xctrl_ui.menu.Menu.OsdTab")
        self.patcher_input_tab = patch("src.v3xctrl_ui.menu.Menu.InputTab")
        self.patcher_frequencies_tab = patch("src.v3xctrl_ui.menu.Menu.FrequenciesTab")
        self.patcher_streamer_tab = patch("src.v3xctrl_ui.menu.Menu.StreamerTab")

        self.mock_general_tab = self.patcher_general_tab.start()
        self.mock_osd_tab = self.patcher_osd_tab.start()
        self.mock_input_tab = self.patcher_input_tab.start()
        self.mock_frequencies_tab = self.patcher_frequencies_tab.start()
        self.mock_streamer_tab = self.patcher_streamer_tab.start()

        # Mock Button
        self.patcher_button = patch("src.v3xctrl_ui.menu.Menu.Button")
        self.mock_button_class = self.patcher_button.start()
        self.mock_button = MagicMock()
        self.mock_button_class.return_value = self.mock_button

        # Mock MAIN_FONT
        self.patcher_font = patch("src.v3xctrl_ui.menu.Menu.MAIN_FONT")
        self.mock_font = self.patcher_font.start()
        self.mock_font.render.return_value = (MagicMock(), MagicMock())

        # Mock sys for quit functionality
        self.patcher_sys = patch("src.v3xctrl_ui.menu.Menu.sys")
        self.mock_sys = self.patcher_sys.start()

        # Create mock dependencies
        self.mock_gamepad_manager = MagicMock()
        self.mock_settings = MagicMock()
        self.mock_callback = MagicMock()
        self.mock_server = MagicMock()

        # Create menu instance
        self.menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

    def tearDown(self):
        self.patcher_pygame.stop()
        self.patcher_general_tab.stop()
        self.patcher_osd_tab.stop()
        self.patcher_input_tab.stop()
        self.patcher_frequencies_tab.stop()
        self.patcher_streamer_tab.stop()
        self.patcher_button.stop()
        self.patcher_font.stop()
        self.patcher_sys.stop()

    def test_initialization(self):
        # Test that menu initializes with correct properties
        self.assertEqual(self.menu.width, 800)
        self.assertEqual(self.menu.height, 600)
        self.assertEqual(self.menu.active_tab, "General")
        self.assertFalse(self.menu.disable_tabs)
        self.assertEqual(len(self.menu.tabs), 5)

    def test_tab_creation(self):
        # Test that all tabs are created with correct names
        tab_names = [tab.name for tab in self.menu.tabs]
        expected_names = ["General", "OSD", "Frequencies", "Input", "Streamer"]
        self.assertEqual(tab_names, expected_names)

    def test_get_active_tab(self):
        # Test getting the active tab
        active_tab = self.menu._get_active_tab()
        self.assertIsNotNone(active_tab)
        self.assertEqual(active_tab.name, "General")

    def test_save_button_callback(self):
        # Mock the active tab view to return settings
        mock_tab_view = MagicMock()
        mock_tab_view.get_settings.return_value = {"key1": "value1", "key2": "value2"}
        self.menu.tabs[0] = self.menu.tabs[0]._replace(view=mock_tab_view)

        # Call save button callback
        self.menu._save_button_callback()

        # Verify settings were saved
        mock_tab_view.get_settings.assert_called_once()
        self.mock_settings.set.assert_any_call("key1", "value1")
        self.mock_settings.set.assert_any_call("key2", "value2")
        self.mock_settings.save.assert_called_once()

    def test_exit_button_callback(self):
        # Set active tab to something other than first
        self.menu.active_tab = "Input"

        # Call exit button callback
        self.menu._exit_button_callback()

        # Verify active tab is reset and callback is called
        self.assertEqual(self.menu.active_tab, "General")
        self.mock_callback.assert_called_once()

    def test_quit_button_callback(self):
        # Call quit button callback
        self.menu._quit_button_callback()

        # Verify pygame quit and sys exit are called
        self.mock_pygame.quit.assert_called_once()
        self.mock_sys.exit.assert_called_once()

    def test_on_active_toggle_active(self):
        # Test when toggled to active
        self.menu._on_active_toggle(True)

        self.assertTrue(self.menu.disable_tabs)
        self.mock_button.disable.assert_called()

    def test_on_active_toggle_inactive(self):
        # Test when toggled to inactive
        self.menu._on_active_toggle(False)

        self.assertFalse(self.menu.disable_tabs)
        self.mock_button.enable.assert_called()

    def test_on_send_command_with_server(self):
        # Test sending command when server is available
        mock_command = MagicMock()
        mock_callback = MagicMock()

        self.menu._on_send_command(mock_command, mock_callback)

        self.mock_server.send_command.assert_called_once_with(mock_command, mock_callback)

    @patch("src.v3xctrl_ui.menu.Menu.logging")
    def test_on_send_command_without_server(self, mock_logging):
        # Test sending command when server is not available
        self.menu.server = None
        mock_command = MagicMock()
        mock_callback = MagicMock()

        self.menu._on_send_command(mock_command, mock_callback)

        mock_logging.error.assert_called_once()

    def test_handle_event_button_events(self):
        # Create mock event
        mock_event = MagicMock()

        # Handle event
        self.menu.handle_event(mock_event)

        # Verify all buttons handle the event
        self.assertEqual(self.mock_button.handle_event.call_count, 3)

    def test_handle_event_tab_click_disabled(self):
        # Disable tabs
        self.menu.disable_tabs = True
        original_active = self.menu.active_tab

        # Create mock mouse click event
        mock_event = MagicMock()
        mock_event.type = pygame.MOUSEBUTTONDOWN
        mock_event.button = 1
        mock_event.pos = (100, 30)

        # Reset all tab rects to return False first
        for tab in self.menu.tabs:
            tab.rect.collidepoint.return_value = False

        # Make the Input tab (index 3) return True for collision
        self.menu.tabs[3].rect.collidepoint.return_value = True

        # Handle event
        self.menu.handle_event(mock_event)

        # Verify active tab didn't change (should still be General)
        self.assertEqual(self.menu.active_tab, original_active)

    def test_draw(self):
        # Create mock surface
        mock_surface = MagicMock()

        # Call draw
        self.menu.draw(mock_surface)

        # Verify surface operations
        mock_surface.blit.assert_called()
        self.mock_pygame.draw.rect.assert_called()
        self.assertEqual(self.mock_button.draw.call_count, 3)

    def test_draw_tabs(self):
        # Create mock surface
        mock_surface = MagicMock()

        # Call draw tabs
        self.menu._draw_tabs(mock_surface)

        # Verify drawing operations
        self.mock_pygame.draw.rect.assert_called()
        self.mock_pygame.draw.line.assert_called()
        mock_surface.blit.assert_called()


if __name__ == "__main__":
    unittest.main()