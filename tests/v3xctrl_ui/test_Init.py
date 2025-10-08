import unittest
from unittest.mock import Mock, patch

import pygame

from src.v3xctrl_control.message import Message
from src.v3xctrl_control.State import State
from src.v3xctrl_ui.Init import Init


class TestInit(unittest.TestCase):
    @patch('src.v3xctrl_ui.Init.Settings')
    def test_settings_creates_and_saves_settings(self, mock_settings_class):
        mock_settings_instance = Mock()
        mock_settings_class.return_value = mock_settings_instance

        result = Init.settings("test_path.toml")

        mock_settings_class.assert_called_once_with("test_path.toml")
        mock_settings_instance.save.assert_called_once()
        self.assertEqual(result, mock_settings_instance)

    @patch('src.v3xctrl_ui.Init.Settings')
    def test_settings_with_default_path(self, mock_settings_class):
        mock_settings_instance = Mock()
        mock_settings_class.return_value = mock_settings_instance

        result = Init.settings()

        mock_settings_class.assert_called_once_with("settings.toml")
        mock_settings_instance.save.assert_called_once()
        self.assertEqual(result, mock_settings_instance)

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_initialization_success(self, mock_server_class):
        mock_server_instance = Mock()
        mock_server_class.return_value = mock_server_instance

        mock_message = Mock(spec=Message)
        mock_state = Mock(spec=State)
        message_callback = Mock()
        state_callback = Mock()

        message_handlers = [(mock_message, message_callback)]
        state_handlers = [(mock_state, state_callback)]

        result = Init.server(8080, message_handlers, state_handlers, 200)

        mock_server_class.assert_called_once_with(8080, 200)
        mock_server_instance.subscribe.assert_called_once_with(mock_message, message_callback)
        mock_server_instance.on.assert_called_once_with(mock_state, state_callback)
        mock_server_instance.start.assert_called_once()
        self.assertEqual(result, mock_server_instance)

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_with_default_udp_ttl(self, mock_server_class):
        mock_server_instance = Mock()
        mock_server_class.return_value = mock_server_instance

        result = Init.server(8080, [], [])

        mock_server_class.assert_called_once_with(8080, 100)
        self.assertEqual(result, mock_server_instance)

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_empty_handlers(self, mock_server_class):
        mock_server_instance = Mock()
        mock_server_class.return_value = mock_server_instance

        result = Init.server(8080, [], [])

        mock_server_instance.subscribe.assert_not_called()
        mock_server_instance.on.assert_not_called()
        mock_server_instance.start.assert_called_once()
        self.assertEqual(result, mock_server_instance)

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_multiple_handlers(self, mock_server_class):
        mock_server_instance = Mock()
        mock_server_class.return_value = mock_server_instance

        msg1, msg2 = Mock(spec=Message), Mock(spec=Message)
        state1, state2 = Mock(spec=State), Mock(spec=State)
        cb1, cb2, cb3, cb4 = Mock(), Mock(), Mock(), Mock()

        message_handlers = [(msg1, cb1), (msg2, cb2)]
        state_handlers = [(state1, cb3), (state2, cb4)]

        result = Init.server(8080, message_handlers, state_handlers)

        self.assertEqual(mock_server_instance.subscribe.call_count, 2)
        self.assertEqual(mock_server_instance.on.call_count, 2)
        mock_server_instance.subscribe.assert_any_call(msg1, cb1)
        mock_server_instance.subscribe.assert_any_call(msg2, cb2)
        mock_server_instance.on.assert_any_call(state1, cb3)
        mock_server_instance.on.assert_any_call(state2, cb4)

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_os_error_port_in_use(self, mock_server_class):
        os_error = OSError("Address already in use")
        os_error.errno = 98
        mock_server_class.side_effect = os_error

        with self.assertRaises(RuntimeError) as cm:
            Init.server(8080, [], [])

        self.assertEqual(str(cm.exception), "Control port already in use")

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_os_error_generic(self, mock_server_class):
        os_error = OSError("Generic error")
        os_error.errno = 1
        mock_server_class.side_effect = os_error

        with self.assertRaises(RuntimeError) as cm:
            Init.server(8080, [], [])

        self.assertEqual(str(cm.exception), "Server error: Generic error")

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_os_error_no_errno(self, mock_server_class):
        os_error = OSError("Error without errno")
        mock_server_class.side_effect = os_error

        with self.assertRaises(RuntimeError) as cm:
            Init.server(8080, [], [])

        self.assertEqual(str(cm.exception), "Server error: Error without errno")

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_start_failure_after_creation(self, mock_server_class):
        mock_server_instance = Mock()
        mock_server_instance.start.side_effect = RuntimeError("Start failed")
        mock_server_class.return_value = mock_server_instance

        with self.assertRaises(RuntimeError):
            Init.server(8080, [], [])

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_subscribe_failure(self, mock_server_class):
        mock_server_instance = Mock()
        mock_server_instance.subscribe.side_effect = RuntimeError("Subscribe failed")
        mock_server_class.return_value = mock_server_instance

        mock_message = Mock(spec=Message)
        message_callback = Mock()
        message_handlers = [(mock_message, message_callback)]

        with self.assertRaises(RuntimeError):
            Init.server(8080, message_handlers, [])

    @patch('src.v3xctrl_ui.Init.Server')
    def test_server_state_handler_failure(self, mock_server_class):
        mock_server_instance = Mock()
        mock_server_instance.on.side_effect = RuntimeError("State handler failed")
        mock_server_class.return_value = mock_server_instance

        mock_state = Mock(spec=State)
        state_callback = Mock()
        state_handlers = [(mock_state, state_callback)]

        with self.assertRaises(RuntimeError):
            Init.server(8080, [], state_handlers)

    @patch('src.v3xctrl_ui.Init.pygame.key.set_repeat')
    @patch('src.v3xctrl_ui.Init.pygame.scrap.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.scrap.init')
    @patch('src.v3xctrl_ui.Init.pygame.time.Clock')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_caption')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.init')
    def test_ui_initialization_success(self, mock_pygame_init, mock_set_mode,
                                     mock_set_caption, mock_clock_class,
                                     mock_scrap_init, mock_scrap_set_mode,
                                     mock_key_set_repeat):
        mock_screen = Mock()
        mock_clock = Mock()
        mock_set_mode.return_value = mock_screen
        mock_clock_class.return_value = mock_clock

        size = (800, 600)
        title = "Test Window"

        screen, clock = Init.ui(size, title)

        mock_pygame_init.assert_called_once()
        expected_flags = pygame.DOUBLEBUF | pygame.SCALED
        mock_set_mode.assert_called_once_with(size, expected_flags)
        mock_set_caption.assert_called_once_with(title)
        mock_clock_class.assert_called_once()
        mock_scrap_init.assert_called_once()
        mock_scrap_set_mode.assert_called_once_with(pygame.SCRAP_CLIPBOARD)
        mock_key_set_repeat.assert_called_once_with(400, 40)

        self.assertEqual(screen, mock_screen)
        self.assertEqual(clock, mock_clock)

    @patch('src.v3xctrl_ui.Init.pygame.init')
    def test_ui_pygame_init_failure(self, mock_pygame_init):
        mock_pygame_init.side_effect = pygame.error("Init failed")

        with self.assertRaises(pygame.error):
            Init.ui((800, 600), "Test")

    @patch('src.v3xctrl_ui.Init.pygame.display.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.init')
    def test_ui_display_mode_failure(self, mock_pygame_init, mock_set_mode):
        mock_set_mode.side_effect = pygame.error("Display mode failed")

        with self.assertRaises(pygame.error):
            Init.ui((800, 600), "Test")

    @patch('src.v3xctrl_ui.Init.pygame.display.set_caption')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.init')
    def test_ui_display_caption_failure(self, mock_pygame_init, mock_set_mode,
                                       mock_set_caption):
        mock_screen = Mock()
        mock_set_mode.return_value = mock_screen
        mock_set_caption.side_effect = pygame.error("Caption failed")

        with self.assertRaises(pygame.error):
            Init.ui((800, 600), "Test")

    @patch('src.v3xctrl_ui.Init.pygame.time.Clock')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_caption')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.init')
    def test_ui_clock_creation_failure(self, mock_pygame_init, mock_set_mode,
                                      mock_set_caption, mock_clock_class):
        mock_screen = Mock()
        mock_set_mode.return_value = mock_screen
        mock_clock_class.side_effect = pygame.error("Clock creation failed")

        with self.assertRaises(pygame.error):
            Init.ui((800, 600), "Test")

    @patch('src.v3xctrl_ui.Init.pygame.scrap.init')
    @patch('src.v3xctrl_ui.Init.pygame.time.Clock')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_caption')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.init')
    def test_ui_scrap_init_failure(self, mock_pygame_init, mock_set_mode,
                                  mock_set_caption, mock_clock_class,
                                  mock_scrap_init):
        mock_scrap_init.side_effect = pygame.error("Clipboard init failed")
        mock_screen = Mock()
        mock_set_mode.return_value = mock_screen
        mock_clock_class.return_value = Mock()

        with self.assertRaises(pygame.error):
            Init.ui((800, 600), "Test")

    @patch('src.v3xctrl_ui.Init.pygame.scrap.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.scrap.init')
    @patch('src.v3xctrl_ui.Init.pygame.time.Clock')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_caption')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.init')
    def test_ui_scrap_set_mode_failure(self, mock_pygame_init, mock_set_mode,
                                      mock_set_caption, mock_clock_class,
                                      mock_scrap_init, mock_scrap_set_mode):
        mock_screen = Mock()
        mock_set_mode.return_value = mock_screen
        mock_clock_class.return_value = Mock()
        mock_scrap_set_mode.side_effect = pygame.error("Clipboard set_mode failed")

        with self.assertRaises(pygame.error):
            Init.ui((800, 600), "Test")

    @patch('src.v3xctrl_ui.Init.pygame.key.set_repeat')
    @patch('src.v3xctrl_ui.Init.pygame.scrap.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.scrap.init')
    @patch('src.v3xctrl_ui.Init.pygame.time.Clock')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_caption')
    @patch('src.v3xctrl_ui.Init.pygame.display.set_mode')
    @patch('src.v3xctrl_ui.Init.pygame.init')
    def test_ui_key_set_repeat_failure(self, mock_pygame_init, mock_set_mode,
                                      mock_set_caption, mock_clock_class,
                                      mock_scrap_init, mock_scrap_set_mode,
                                      mock_key_set_repeat):
        mock_screen = Mock()
        mock_clock = Mock()
        mock_set_mode.return_value = mock_screen
        mock_clock_class.return_value = mock_clock
        mock_key_set_repeat.side_effect = pygame.error("Key repeat failed")

        with self.assertRaises(pygame.error):
            Init.ui((800, 600), "Test")

    @patch('src.v3xctrl_ui.Init.VideoReceiver')
    def test_video_receiver_initialization_success(self, mock_video_receiver_class):
        mock_video_receiver = Mock()
        mock_video_receiver_class.return_value = mock_video_receiver
        mock_error_callback = Mock()

        result = Init.video_receiver(9090, mock_error_callback, 0)

        mock_video_receiver_class.assert_called_once_with(9090, mock_error_callback, render_ratio=0)
        mock_video_receiver.start.assert_called_once()
        self.assertEqual(result, mock_video_receiver)

    @patch('src.v3xctrl_ui.Init.VideoReceiver')
    def test_video_receiver_creation_failure(self, mock_video_receiver_class):
        mock_video_receiver_class.side_effect = RuntimeError("Creation failed")
        mock_error_callback = Mock()

        with self.assertRaises(RuntimeError):
            Init.video_receiver(9090, mock_error_callback, 0)

    @patch('src.v3xctrl_ui.Init.VideoReceiver')
    def test_video_receiver_start_failure(self, mock_video_receiver_class):
        mock_video_receiver = Mock()
        mock_video_receiver.start.side_effect = RuntimeError("Start failed")
        mock_video_receiver_class.return_value = mock_video_receiver
        mock_error_callback = Mock()

        with self.assertRaises(RuntimeError):
            Init.video_receiver(9090, mock_error_callback, 0)

    @patch('src.v3xctrl_ui.Init.VideoReceiver')
    def test_video_receiver_with_different_ports(self, mock_video_receiver_class):
        mock_video_receiver = Mock()
        mock_video_receiver_class.return_value = mock_video_receiver
        mock_error_callback = Mock()

        Init.video_receiver(0, mock_error_callback, 0)
        mock_video_receiver_class.assert_called_with(0, mock_error_callback, render_ratio=0)

        mock_video_receiver_class.reset_mock()
        Init.video_receiver(65535, mock_error_callback, 0)
        mock_video_receiver_class.assert_called_with(65535, mock_error_callback, render_ratio=0)

    @patch('src.v3xctrl_ui.Init.VideoReceiver')
    def test_video_receiver_with_none_callback(self, mock_video_receiver_class):
        mock_video_receiver = Mock()
        mock_video_receiver_class.return_value = mock_video_receiver

        result = Init.video_receiver(9090, None, 0)

        mock_video_receiver_class.assert_called_once_with(9090, None, render_ratio=0)
        mock_video_receiver.start.assert_called_once()
        self.assertEqual(result, mock_video_receiver)


if __name__ == '__main__':
    unittest.main()
