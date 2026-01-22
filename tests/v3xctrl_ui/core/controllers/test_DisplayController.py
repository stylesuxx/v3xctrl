import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame

from v3xctrl_ui.core.controllers.DisplayController import DisplayController
from v3xctrl_ui.core.dataclasses import ApplicationModel


class TestDisplayController(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.model = ApplicationModel(fullscreen=False)
        self.base_size = (800, 600)
        self.title = "Test App"

    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.list_modes")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_mode")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_caption")
    def test_initialization_windowed(self, mock_caption, mock_set_mode, mock_list_modes):
        """Test DisplayManager initializes in windowed mode."""
        mock_screen = MagicMock()
        mock_screen.get_size.return_value = (800, 600)
        mock_set_mode.return_value = mock_screen

        display_manager = DisplayController(self.model, self.base_size, self.title)

        # Should set caption
        mock_caption.assert_called_once_with(self.title)

        # Should create windowed mode
        mock_set_mode.assert_called_once()
        call_args = mock_set_mode.call_args
        self.assertEqual(call_args[0][0], (800, 600))
        # Check flags contain DOUBLEBUF and SCALED
        flags = call_args[0][1]
        self.assertTrue(flags & pygame.DOUBLEBUF)
        self.assertTrue(flags & pygame.SCALED)

        # Should set scale to 1.0 for windowed
        self.assertEqual(self.model.scale, 1.0)
        self.assertFalse(self.model.fullscreen)

    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.list_modes")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_mode")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_caption")
    def test_initialization_fullscreen(self, mock_caption, mock_set_mode, mock_list_modes):
        """Test DisplayManager initializes in fullscreen mode."""
        self.model.fullscreen = True

        mock_screen = MagicMock()
        mock_screen.get_size.return_value = (1920, 1080)
        mock_set_mode.return_value = mock_screen
        mock_list_modes.return_value = [(1920, 1080), (1280, 720)]

        display_manager = DisplayController(self.model, self.base_size, self.title)

        # Should set caption
        mock_caption.assert_called_once_with(self.title)

        # Should create fullscreen mode
        mock_set_mode.assert_called_once()
        call_args = mock_set_mode.call_args
        self.assertEqual(call_args[0][0], (1920, 1080))

        # Check flags contain DOUBLEBUF, SCALED, and FULLSCREEN
        flags = call_args[0][1]
        self.assertTrue(flags & pygame.DOUBLEBUF)
        self.assertTrue(flags & pygame.SCALED)
        self.assertTrue(flags & pygame.FULLSCREEN)

        # Should calculate scale based on aspect ratio
        expected_scale = min(1920 / 800, 1080 / 600)
        self.assertEqual(self.model.scale, expected_scale)
        self.assertTrue(self.model.fullscreen)

    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.list_modes")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_mode")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_caption")
    def test_toggle_fullscreen(self, mock_caption, mock_set_mode, mock_list_modes):
        """Test toggling between windowed and fullscreen."""
        mock_screen = MagicMock()
        mock_screen.get_size.return_value = (800, 600)
        mock_set_mode.return_value = mock_screen
        mock_list_modes.return_value = [(1920, 1080)]

        display_manager = DisplayController(self.model, self.base_size, self.title)

        # Start in windowed mode
        self.assertFalse(self.model.fullscreen)
        self.assertEqual(mock_set_mode.call_count, 1)

        # Toggle to fullscreen
        display_manager.toggle_fullscreen()
        self.assertTrue(self.model.fullscreen)
        self.assertEqual(mock_set_mode.call_count, 2)

        # Toggle back to windowed
        display_manager.toggle_fullscreen()
        self.assertFalse(self.model.fullscreen)
        self.assertEqual(mock_set_mode.call_count, 3)

    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.list_modes")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_mode")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_caption")
    def test_set_fullscreen(self, mock_caption, mock_set_mode, mock_list_modes):
        """Test explicitly setting fullscreen mode."""
        mock_screen = MagicMock()
        mock_screen.get_size.return_value = (800, 600)
        mock_set_mode.return_value = mock_screen
        mock_list_modes.return_value = [(1920, 1080)]

        display_manager = DisplayController(self.model, self.base_size, self.title)

        # Set fullscreen explicitly
        display_manager.set_fullscreen(True)
        self.assertTrue(self.model.fullscreen)

        # Set windowed explicitly
        display_manager.set_fullscreen(False)
        self.assertFalse(self.model.fullscreen)

        # Setting to same value shouldn't trigger update
        initial_call_count = mock_set_mode.call_count
        display_manager.set_fullscreen(False)
        self.assertEqual(mock_set_mode.call_count, initial_call_count)

    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.list_modes")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_mode")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_caption")
    def test_get_methods(self, mock_caption, mock_set_mode, mock_list_modes):
        """Test getter methods."""
        mock_screen = MagicMock()
        mock_screen.get_size.return_value = (800, 600)
        mock_set_mode.return_value = mock_screen

        display_manager = DisplayController(self.model, self.base_size, self.title)

        # Test getters
        self.assertEqual(display_manager.get_screen(), mock_screen)
        self.assertEqual(display_manager.get_size(), (800, 600))
        self.assertEqual(display_manager.get_base_size(), (800, 600))
        self.assertEqual(display_manager.get_scale(), 1.0)

    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.list_modes")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_mode")
    @patch("v3xctrl_ui.core.controllers.DisplayController.pygame.display.set_caption")
    def test_scale_calculation(self, mock_caption, mock_set_mode, mock_list_modes):
        """Test that scale is calculated correctly for various resolutions."""
        self.model.fullscreen = True

        # Test with resolution that matches width constraint
        mock_list_modes.return_value = [(1600, 1200)]
        mock_screen = MagicMock()
        mock_screen.get_size.return_value = (1600, 1200)
        mock_set_mode.return_value = mock_screen

        display_manager = DisplayController(self.model, self.base_size, self.title)

        # Scale should be min(1600/800, 1200/600) = min(2.0, 2.0) = 2.0
        self.assertEqual(self.model.scale, 2.0)


if __name__ == '__main__':
    unittest.main()
