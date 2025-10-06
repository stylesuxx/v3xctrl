# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch
import pygame

from v3xctrl_ui.menu.tabs.StreamerTab import StreamerTab
from v3xctrl_ui.Settings import Settings


class TestStreamerTab(unittest.TestCase):
    def setUp(self):
        # Initialize pygame for surface creation
        pygame.init()
        pygame.display.set_mode((1, 1))  # Minimal display for testing

        # Mock dependencies
        self.mock_settings = MagicMock(spec=Settings)
        self.mock_on_active_toggle = MagicMock()
        self.mock_send_command = MagicMock()

        # Test parameters
        self.width = 800
        self.height = 600
        self.padding = 10
        self.y_offset = 20

        # Create StreamerTab instance
        self.tab = StreamerTab(
            settings=self.mock_settings,
            width=self.width,
            height=self.height,
            padding=self.padding,
            y_offset=self.y_offset,
            on_active_toggle=self.mock_on_active_toggle,
            send_command=self.mock_send_command
        )

    def test_initialization(self):
        """Test that StreamerTab initializes correctly"""
        self.assertEqual(self.tab.on_active_toggle, self.mock_on_active_toggle)
        self.assertEqual(self.tab.send_command, self.mock_send_command)
        self.assertFalse(self.tab.disabled)

        # Check that buttons are created
        self.assertIsNotNone(self.tab.video_stop_button)
        self.assertIsNotNone(self.tab.video_start_button)
        self.assertIsNotNone(self.tab.shutdown_button)

        # Check that buttons are added to elements
        self.assertEqual(len(self.tab.elements), 3)
        self.assertIn(self.tab.video_stop_button, self.tab.elements)
        self.assertIn(self.tab.video_start_button, self.tab.elements)
        self.assertIn(self.tab.shutdown_button, self.tab.elements)

    def test_button_labels(self):
        """Test that buttons have correct labels"""
        # Note: We can't easily test the actual button text without accessing
        # internal Button implementation, but we can verify they were created
        # with the expected parameters through their callbacks
        self.assertEqual(self.tab.video_stop_button.callback, self.tab._on_stop_video)
        self.assertEqual(self.tab.video_start_button.callback, self.tab._on_start_video)
        self.assertEqual(self.tab.shutdown_button.callback, self.tab._on_shutdown)

    def test_stop_video_action(self):
        """Test stop video button functionality"""
        self.tab._on_stop_video()

        # Check that UI is disabled
        self.assertTrue(self.tab.disabled)
        self.mock_on_active_toggle.assert_called_once_with(True)

        # Check that command is sent
        self.mock_send_command.assert_called_once()

        # Get the actual command that was sent
        call_args = self.mock_send_command.call_args
        sent_command = call_args[0][0]
        callback = call_args[0][1]

        # Compare command and parameters separately (ignore auto-generated ID)
        self.assertEqual(sent_command.command, "service")
        self.assertEqual(sent_command.parameters, {
            "action": "stop",
            "name": "v3xctrl-video",
        })
        self.assertEqual(callback, self.tab._on_command_callback)

    def test_start_video_action(self):
        """Test start video button functionality"""
        self.tab._on_start_video()

        # Check that UI is disabled
        self.assertTrue(self.tab.disabled)
        self.mock_on_active_toggle.assert_called_once_with(True)

        # Check that command is sent
        self.mock_send_command.assert_called_once()

        # Get the actual command that was sent
        call_args = self.mock_send_command.call_args
        sent_command = call_args[0][0]

        # Compare command and parameters separately (ignore auto-generated ID)
        self.assertEqual(sent_command.command, "service")
        self.assertEqual(sent_command.parameters, {
            "action": "start",
            "name": "v3xctrl-video",
        })

    def test_shutdown_action(self):
        """Test shutdown button functionality"""
        self.tab._on_shutdown()

        # Check that UI is disabled
        self.assertTrue(self.tab.disabled)
        self.mock_on_active_toggle.assert_called_once_with(True)

        # Check that command is sent
        self.mock_send_command.assert_called_once()

        # Get the actual command that was sent
        call_args = self.mock_send_command.call_args
        sent_command = call_args[0][0]

        # Compare command directly (shutdown command likely has no parameters)
        self.assertEqual(sent_command.command, "shutdown")

    def test_video_action_disables_elements(self):
        """Test that video actions disable all UI elements"""
        # Mock the elements to test disable calls
        for element in self.tab.elements:
            element.disable = MagicMock()

        self.tab._on_video_action("start")

        # Check all elements were disabled
        for element in self.tab.elements:
            element.disable.assert_called_once()

    def test_shutdown_disables_elements(self):
        """Test that shutdown disables all UI elements"""
        # Mock the elements to test disable calls
        for element in self.tab.elements:
            element.disable = MagicMock()

        self.tab._on_shutdown()

        # Check all elements were disabled
        for element in self.tab.elements:
            element.disable.assert_called_once()

    @patch('time.sleep')
    def test_command_callback_success(self, mock_sleep):
        """Test command callback with successful status"""
        # Mock the elements to test enable calls
        for element in self.tab.elements:
            element.enable = MagicMock()

        # Set tab to disabled state first
        self.tab.disabled = True

        # Call the callback with success
        self.tab._on_command_callback(True)

        # Check that sleep was called
        mock_sleep.assert_called_once_with(1)

        # Check that UI is re-enabled
        self.assertFalse(self.tab.disabled)
        self.mock_on_active_toggle.assert_called_with(False)

        # Check all elements were enabled
        for element in self.tab.elements:
            element.enable.assert_called_once()

    @patch('time.sleep')
    def test_command_callback_failure(self, mock_sleep):
        """Test command callback with failed status"""
        # Mock the elements to test enable calls
        for element in self.tab.elements:
            element.enable = MagicMock()

        # Set tab to disabled state first
        self.tab.disabled = True

        # Call the callback with failure
        self.tab._on_command_callback(False)

        # Check that sleep was called
        mock_sleep.assert_called_once_with(1)

        # Check that UI is re-enabled regardless of status
        self.assertFalse(self.tab.disabled)
        self.mock_on_active_toggle.assert_called_with(False)

        # Check all elements were enabled
        for element in self.tab.elements:
            element.enable.assert_called_once()

    @patch('time.sleep')
    @patch('logging.debug')
    def test_command_callback_logs_status(self, mock_log_debug, mock_sleep):
        """Test that command callback logs the status"""
        self.tab._on_command_callback(True)
        mock_log_debug.assert_called_once_with("Received command status: True")

        mock_log_debug.reset_mock()
        self.tab._on_command_callback(False)
        mock_log_debug.assert_called_once_with("Received command status: False")

    def test_draw_method(self):
        """Test that draw method can be called without errors"""
        surface = pygame.Surface((self.width, self.height))

        # Mock the button draw methods to avoid font/rendering issues
        self.tab.video_start_button.draw = MagicMock()
        self.tab.video_stop_button.draw = MagicMock()
        self.tab.shutdown_button.draw = MagicMock()
        self.tab.video_start_button.get_size = MagicMock(return_value=(150, 40))
        self.tab.video_stop_button.get_size = MagicMock(return_value=(150, 40))
        self.tab.shutdown_button.get_size = MagicMock(return_value=(150, 40))
        self.tab.video_start_button.set_position = MagicMock()
        self.tab.video_stop_button.set_position = MagicMock()
        self.tab.shutdown_button.set_position = MagicMock()

        # Mock the headline drawing method
        self.tab._draw_headline = MagicMock()

        # Should not raise an exception
        self.tab.draw(surface)

        # Verify buttons were positioned and drawn
        self.tab.video_start_button.set_position.assert_called_once()
        self.tab.video_stop_button.set_position.assert_called_once()
        self.tab.shutdown_button.set_position.assert_called_once()

        self.tab.video_start_button.draw.assert_called_once_with(surface)
        self.tab.video_stop_button.draw.assert_called_once_with(surface)
        self.tab.shutdown_button.draw.assert_called_once_with(surface)

    def test_get_settings_returns_empty_dict(self):
        """Test that get_settings returns an empty dictionary"""
        settings = self.tab.get_settings()
        self.assertEqual(settings, {})
        self.assertIsInstance(settings, dict)

    def test_multiple_rapid_commands(self):
        """Test behavior when multiple commands are sent rapidly"""
        # First command
        self.tab._on_start_video()
        self.assertTrue(self.tab.disabled)

        # Second command while first is still processing
        self.tab._on_stop_video()

        # Should still be disabled and send_command should be called twice
        self.assertTrue(self.tab.disabled)
        self.assertEqual(self.mock_send_command.call_count, 2)

    def test_video_action_generic(self):
        """Test the generic _on_video_action method"""
        test_action = "restart"

        self.tab._on_video_action(test_action)

        # Check that UI is disabled
        self.assertTrue(self.tab.disabled)
        self.mock_on_active_toggle.assert_called_once_with(True)

        # Check that command is sent
        self.mock_send_command.assert_called_once()

        call_args = self.mock_send_command.call_args
        sent_command = call_args[0][0]

        # Compare command and parameters separately (ignore auto-generated ID)
        self.assertEqual(sent_command.command, "service")
        self.assertEqual(sent_command.parameters, {
            "action": test_action,
            "name": "v3xctrl-video",
        })


if __name__ == '__main__':
    unittest.main()
