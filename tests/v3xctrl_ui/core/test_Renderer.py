"""Tests for Renderer - handles all rendering logic for the application."""
import os
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pygame

# Set SDL to use dummy video driver before importing pygame
os.environ['SDL_VIDEODRIVER'] = 'dummy'

from v3xctrl_ui.core.Renderer import Renderer


class TestRenderer(unittest.TestCase):
    """Test Renderer initialization and rendering methods."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((1280, 720))

        self.settings = MagicMock()
        self.settings.get.return_value = {"fullscreen": False}

        self.size = (1280, 720)

    def tearDown(self):
        """Clean up pygame."""
        # Don't call pygame.quit() to avoid font invalidation issues
        # between tests. pygame.init() is idempotent so it's safe to
        # call multiple times without quit.
        pass

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    def test_initialization(self, mock_get_ip):
        """Test Renderer initialization."""
        mock_get_ip.return_value = "192.168.1.100"

        renderer = Renderer(self.size, self.settings)

        assert renderer.video_width == 1280
        assert renderer.video_height == 720
        assert renderer.video_size == (1280, 720)
        assert renderer.settings == self.settings
        assert renderer.ip == "192.168.1.100"
        assert isinstance(renderer.video_surface, pygame.Surface)
        assert renderer.last_frame_id is None

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    def test_get_video_frame_with_receiver(self, mock_get_ip):
        """Test _get_video_frame when video receiver exists."""
        mock_get_ip.return_value = "192.168.1.100"
        renderer = Renderer(self.size, self.settings)

        network_manager = MagicMock()
        mock_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        network_manager.video_receiver.get_frame.return_value = mock_frame

        frame = renderer._get_video_frame(network_manager)

        assert frame is not None
        assert frame.shape == (720, 1280, 3)

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    def test_get_video_frame_no_receiver(self, mock_get_ip):
        """Test _get_video_frame when no video receiver."""
        mock_get_ip.return_value = "192.168.1.100"
        renderer = Renderer(self.size, self.settings)

        network_manager = MagicMock()
        network_manager.video_receiver = None

        frame = renderer._get_video_frame(network_manager)

        assert frame is None

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    @patch('v3xctrl_ui.core.Renderer.pygame.display.flip')
    def test_render_all_with_video_frame(self, mock_flip, mock_get_ip):
        """Test render_all when video frame is available."""
        mock_get_ip.return_value = "192.168.1.100"
        renderer = Renderer(self.size, self.settings)

        # Create mocks
        state = MagicMock()
        state.screen = pygame.Surface((1280, 720))
        state.model.control_connected = True
        state.event_controller.menu = None
        state.osd.update_debug_status = MagicMock()
        state.osd.update_data_queue = MagicMock()
        state.osd.set_control = MagicMock()
        state.osd.update_buffer_queue = MagicMock()
        state.osd.render = MagicMock()
        state.model.throttle = 0.5
        state.model.steering = 0.3
        state.model.loop_history = MagicMock()

        network_manager = MagicMock()
        mock_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        network_manager.video_receiver.get_frame.return_value = mock_frame
        network_manager.server_error = None
        network_manager.get_data_queue_size.return_value = 0
        network_manager.get_video_buffer_size.return_value = 0

        renderer.render_all(state, network_manager)

        # Verify rendering completed
        mock_flip.assert_called_once()

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    @patch('v3xctrl_ui.core.Renderer.pygame.display.flip')
    def test_render_all_no_video(self, mock_flip, mock_get_ip):
        """Test render_all when no video frame is available."""
        mock_get_ip.return_value = "192.168.1.100"
        self.settings.get.side_effect = lambda key, default=None: {
            "show_connection_info": True,
            "relay": {"enabled": False},
            "ports": {"video": 6666, "control": 6668}
        }.get(key, default)

        renderer = Renderer(self.size, self.settings)

        state = MagicMock()
        state.screen = pygame.Surface((1280, 720))
        state.model.control_connected = False
        state.event_controller.menu = None
        state.osd.update_debug_status = MagicMock()
        state.osd.update_data_queue = MagicMock()
        state.osd.set_control = MagicMock()
        state.osd.update_buffer_queue = MagicMock()
        state.osd.render = MagicMock()
        state.model.throttle = 0.0
        state.model.steering = 0.0
        state.model.loop_history = MagicMock()

        network_manager = MagicMock()
        network_manager.video_receiver = None
        network_manager.relay_enable = False
        network_manager.relay_status_message = "Waiting for streamer..."
        network_manager.server_error = None
        network_manager.get_data_queue_size.return_value = 0
        network_manager.get_video_buffer_size.return_value = 0

        renderer.render_all(state, network_manager)

        # Verify rendering completed
        mock_flip.assert_called_once()

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    @patch('v3xctrl_ui.core.Renderer.pygame.display.flip')
    def test_render_all_with_server_error(self, mock_flip, mock_get_ip):
        """Test render_all when server has an error."""
        mock_get_ip.return_value = "192.168.1.100"
        self.settings.get.side_effect = lambda key, default=None: {
            "show_connection_info": True,
            "relay": {"enabled": False},
            "ports": {"video": 6666, "control": 6668}
        }.get(key, default)

        renderer = Renderer(self.size, self.settings)

        state = MagicMock()
        state.screen = pygame.Surface((1280, 720))
        state.model.control_connected = True
        state.event_controller.menu = None
        state.osd.update_debug_status = MagicMock()
        state.osd.update_data_queue = MagicMock()
        state.osd.set_control = MagicMock()
        state.osd.update_buffer_queue = MagicMock()
        state.osd.render = MagicMock()
        state.model.throttle = 0.0
        state.model.steering = 0.0
        state.model.loop_history = MagicMock()

        network_manager = MagicMock()
        network_manager.video_receiver = None
        network_manager.relay_enable = False
        network_manager.relay_status_message = ""
        network_manager.server_error = "Control port already in use"
        network_manager.get_data_queue_size.return_value = 0
        network_manager.get_video_buffer_size.return_value = 0

        renderer.render_all(state, network_manager)

        # Verify debug status was updated
        state.osd.update_debug_status.assert_called_with("fail")
        mock_flip.assert_called_once()

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    @patch('v3xctrl_ui.core.Renderer.pygame.display.flip')
    def test_render_all_with_menu(self, mock_flip, mock_get_ip):
        """Test render_all when menu is active."""
        mock_get_ip.return_value = "192.168.1.100"
        self.settings.get.side_effect = lambda key, default=None: {
            "show_connection_info": True,
            "relay": {"enabled": False},
            "ports": {"video": 6666, "control": 6668}
        }.get(key, default)

        renderer = Renderer(self.size, self.settings)

        state = MagicMock()
        state.screen = pygame.Surface((1280, 720))
        state.model.control_connected = True
        state.osd.update_debug_status = MagicMock()
        state.osd.update_data_queue = MagicMock()
        state.osd.set_control = MagicMock()
        state.osd.update_buffer_queue = MagicMock()
        state.osd.render = MagicMock()
        state.model.throttle = 0.0
        state.model.steering = 0.0
        state.model.loop_history = MagicMock()

        # Mock menu
        mock_menu = MagicMock()
        state.event_controller.menu = mock_menu

        network_manager = MagicMock()
        network_manager.video_receiver = None
        network_manager.relay_enable = False
        network_manager.relay_status_message = ""
        network_manager.server_error = None
        network_manager.get_data_queue_size.return_value = 0
        network_manager.get_video_buffer_size.return_value = 0

        renderer.render_all(state, network_manager)

        # Verify menu was drawn
        mock_menu.draw.assert_called_once_with(state.screen)
        mock_flip.assert_called_once()

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    def test_render_video_frame_new_frame(self, mock_get_ip):
        """Test _render_video_frame with a new frame."""
        mock_get_ip.return_value = "192.168.1.100"
        renderer = Renderer(self.size, self.settings)

        screen = pygame.Surface((1280, 720))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        renderer._render_video_frame(screen, frame)

        # Verify frame was processed
        assert renderer.last_frame_id == id(frame)

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    def test_render_video_frame_same_frame(self, mock_get_ip):
        """Test _render_video_frame with the same frame twice."""
        mock_get_ip.return_value = "192.168.1.100"
        renderer = Renderer(self.size, self.settings)

        screen = pygame.Surface((1280, 720))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Render twice
        renderer._render_video_frame(screen, frame)
        frame_id_first = renderer.last_frame_id

        renderer._render_video_frame(screen, frame)
        frame_id_second = renderer.last_frame_id

        # Frame ID should be the same
        assert frame_id_first == frame_id_second

    @patch('v3xctrl_ui.core.Renderer.get_external_ip')
    def test_render_video_frame_fullscreen(self, mock_get_ip):
        """Test _render_video_frame in fullscreen mode."""
        mock_get_ip.return_value = "192.168.1.100"
        renderer = Renderer(self.size, self.settings)
        renderer.fullscreen = True
        renderer.scale = 1.5
        renderer.center_x = 640
        renderer.center_y = 360

        screen = pygame.Surface((1280, 720))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        renderer._render_video_frame(screen, frame)

        # Just verify it doesn't crash in fullscreen mode
        assert renderer.fullscreen is True


if __name__ == '__main__':
    unittest.main()
