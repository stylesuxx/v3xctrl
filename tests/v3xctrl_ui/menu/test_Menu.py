import unittest
from unittest.mock import MagicMock, patch

import pygame

from src.v3xctrl_ui.menu.Menu import Menu


@patch("src.v3xctrl_ui.menu.Menu.pygame")
@patch("src.v3xctrl_ui.menu.Menu.GeneralTab")
@patch("src.v3xctrl_ui.menu.Menu.OsdTab")
@patch("src.v3xctrl_ui.menu.Menu.InputTab")
@patch("src.v3xctrl_ui.menu.Menu.FrequenciesTab")
@patch("src.v3xctrl_ui.menu.Menu.StreamerTab")
@patch("src.v3xctrl_ui.menu.Menu.Button")
@patch("src.v3xctrl_ui.menu.Menu.MAIN_FONT")
@patch("src.v3xctrl_ui.menu.Menu.sys")
class TestMenu(unittest.TestCase):
    def setUp(self):
        self.mock_gamepad_manager = MagicMock()
        self.mock_settings = MagicMock()
        self.mock_callback = MagicMock()
        self.mock_server = MagicMock()

    def _setup_mocks(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                     mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
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
        mock_font.render.return_value = (MagicMock(), MagicMock())

        return mock_pygame, mock_button_class, mock_font, mock_sys

    def test_initialization(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                           mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        self.assertEqual(menu.width, 800)
        self.assertEqual(menu.height, 600)
        self.assertEqual(menu.active_tab, "General")
        self.assertFalse(menu.disable_tabs)
        self.assertEqual(len(menu.tabs), 6)

    def test_tab_creation(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
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

    def test_get_active_tab(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                           mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        active_tab = menu._get_active_tab()
        self.assertIsNotNone(active_tab)
        self.assertEqual(active_tab.name, "General")

    def test_save_button_callback(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                 mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        mock_tab_view = MagicMock()
        mock_tab_view.get_settings.return_value = {"key1": "value1", "key2": "value2"}
        menu.tabs[0] = menu.tabs[0]._replace(view=mock_tab_view)

        menu._save_button_callback()

        mock_tab_view.get_settings.assert_called_once()
        self.mock_settings.set.assert_any_call("key1", "value1")
        self.mock_settings.set.assert_any_call("key2", "value2")
        self.mock_settings.save.assert_called_once()

    def test_exit_button_callback(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                 mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        menu.active_tab = "Input"
        menu._exit_button_callback()

        self.assertEqual(menu.active_tab, "General")
        self.mock_callback.assert_called_once()

    def test_quit_button_callback(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                 mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        mock_pygame, _, _, _ = self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                               mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        menu._quit_button_callback()

        mock_pygame.quit.assert_called_once()
        mock_sys.exit.assert_called_once()

    def test_on_active_toggle_active(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                    mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        menu._on_active_toggle(True)

        self.assertTrue(menu.disable_tabs)
        self.mock_button.disable.assert_called()

    def test_on_active_toggle_inactive(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                      mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        menu._on_active_toggle(False)

        self.assertFalse(menu.disable_tabs)
        self.mock_button.enable.assert_called()

    def test_on_send_command_with_server(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                        mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        mock_command = MagicMock()
        mock_callback = MagicMock()

        menu._on_send_command(mock_command, mock_callback)

        self.mock_server.send_command.assert_called_once_with(mock_command, mock_callback)

    @patch("src.v3xctrl_ui.menu.Menu.logging")
    def test_on_send_command_without_server(self, mock_logging, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                           mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=None
        )

        mock_command = MagicMock()
        mock_callback = MagicMock()

        menu._on_send_command(mock_command, mock_callback)

        mock_logging.error.assert_called_once()

    def test_handle_event_button_events(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                       mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        mock_event = MagicMock()
        menu.handle_event(mock_event)

        self.assertEqual(self.mock_button.handle_event.call_count, 3)

    def test_handle_event_tab_click_disabled(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                            mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        menu.disable_tabs = True
        original_active = menu.active_tab

        mock_event = MagicMock()
        mock_event.type = pygame.MOUSEBUTTONDOWN
        mock_event.button = 1
        mock_event.pos = (100, 30)

        for tab in menu.tabs:
            tab.rect.collidepoint.return_value = False

        menu.tabs[3].rect.collidepoint.return_value = True
        menu.handle_event(mock_event)

        self.assertEqual(menu.active_tab, original_active)

    def test_draw(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                 mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        mock_surface = MagicMock()
        menu.draw(mock_surface)

        mock_surface.blit.assert_called()
        mock_pygame.draw.rect.assert_called()
        self.assertEqual(self.mock_button.draw.call_count, 3)

    def test_draw_tabs(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                      mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        mock_surface = MagicMock()
        menu._draw_tabs(mock_surface)

        mock_pygame.draw.rect.assert_called()
        mock_pygame.draw.line.assert_called()
        mock_surface.blit.assert_called()

    def test_get_active_tab_not_found(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                     mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        menu.active_tab = "NonExistentTab"
        self.assertIsNone(menu._get_active_tab())

    def test_save_button_callback_no_active_tab(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                               mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        menu.active_tab = "NonExistentTab"
        menu._save_button_callback()

        self.mock_settings.set.assert_not_called()
        self.mock_settings.save.assert_not_called()

    def test_handle_event_no_active_tab(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                                       mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        menu.active_tab = "NonExistentTab"
        mock_event = MagicMock()
        menu.handle_event(mock_event)

    def test_draw_no_active_tab(self, mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                               mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame):
        self._setup_mocks(mock_sys, mock_font, mock_button_class, mock_streamer_tab,
                         mock_frequencies_tab, mock_input_tab, mock_osd_tab, mock_general_tab, mock_pygame)

        menu = Menu(
            width=800,
            height=600,
            gamepad_manager=self.mock_gamepad_manager,
            settings=self.mock_settings,
            callback=self.mock_callback,
            server=self.mock_server
        )

        menu.active_tab = "NonExistentTab"
        mock_surface = MagicMock()
        menu.draw(mock_surface)

        mock_surface.blit.assert_called()
        self.assertEqual(self.mock_button.draw.call_count, 3)


if __name__ == "__main__":
    unittest.main()
