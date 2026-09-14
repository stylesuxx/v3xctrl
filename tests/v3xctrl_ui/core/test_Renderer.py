import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from collections import deque
from unittest.mock import MagicMock, patch

import numpy as np
import pygame

from tests.v3xctrl_ui.settings_helper import build_settings
from v3xctrl_ui.core.FrameSnapshot import ConnectionStatus, FrameSnapshot
from v3xctrl_ui.core.Renderer import Renderer


def build_snapshot(**overrides) -> FrameSnapshot:
    """A connected frame with no video, which every case adjusts from."""
    connection_fields = {
        field: overrides.pop(field) for field in list(overrides) if field in ConnectionStatus.__dataclass_fields__
    }
    connection = ConnectionStatus(**{"user_connected": True, "control_connected": True, **connection_fields})

    return FrameSnapshot(connection=connection, loop_history=deque([1.0, 2.0]), **overrides)


class TestRenderer(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((800, 600))

        self.settings = build_settings()
        self.osd = MagicMock()
        self.menu = MagicMock()
        self.screen = pygame.Surface((800, 600))

    def tearDown(self):
        pygame.display.quit()

    def _build_renderer(self) -> Renderer:
        return Renderer((800, 600), self.settings, self.osd, self.menu)

    def test_initialization(self):
        renderer = self._build_renderer()

        self.assertEqual(renderer.video_size, (800, 600))
        self.assertEqual(renderer.video_width, 800)
        self.assertEqual(renderer.video_height, 600)

    @patch("v3xctrl_ui.core.Renderer.get_external_ip", return_value="1.2.3.4")
    def test_ip_is_resolved_on_first_use_only(self, mock_get_ip):
        renderer = self._build_renderer()

        mock_get_ip.assert_not_called()

        self.assertEqual(renderer.ip, "1.2.3.4")
        self.assertEqual(renderer.ip, "1.2.3.4")
        mock_get_ip.assert_called_once()

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_blits_the_video_frame(self, _mock_flip):
        renderer = self._build_renderer()
        frame = np.zeros((600, 800, 3), dtype=np.uint8)

        with patch("v3xctrl_ui.core.Renderer.pygame.surfarray.blit_array") as mock_blit:
            renderer.render(self.screen, build_snapshot(video_frame=frame))

        mock_blit.assert_called_once()

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_without_frame_shows_no_video_signal(self, _mock_flip):
        renderer = self._build_renderer()

        with patch.object(renderer, "_render_no_video_signal_screen") as mock_no_video:
            renderer.render(self.screen, build_snapshot(video_frame=None))

        mock_no_video.assert_called_once()

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_without_control_shows_no_control_signal(self, _mock_flip):
        renderer = self._build_renderer()

        with patch.object(renderer, "_render_no_control_signal_screen") as mock_no_control:
            renderer.render(self.screen, build_snapshot(control_connected=False))

        mock_no_control.assert_called_once()

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_shows_relay_status_when_relay_enabled(self, _mock_flip):
        renderer = self._build_renderer()
        snapshot = build_snapshot(relay_enabled=True, relay_status_message="waiting for streamer")

        with patch.object(renderer, "_render_relay_status_screen") as mock_relay:
            renderer.render(self.screen, snapshot)

        mock_relay.assert_called_once()
        self.assertEqual(mock_relay.call_args[0][0], "WAITING FOR STREAMER")

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_shows_control_error(self, _mock_flip):
        renderer = self._build_renderer()

        with patch.object(renderer, "_render_error_text") as mock_error:
            renderer.render(self.screen, build_snapshot(control_error="Control port already in use"))

        mock_error.assert_called_once_with(self.screen, "Control port already in use")

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_draws_osd_from_snapshot_histories(self, _mock_flip):
        renderer = self._build_renderer()
        video_history = deque([3.0])
        snapshot = build_snapshot(video_history=video_history)

        renderer.render(self.screen, snapshot)

        self.osd.render.assert_called_once_with(self.screen, snapshot.loop_history, video_history)

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_never_writes_to_the_osd(self, _mock_flip):
        """Per-frame OSD values are written by the caller, never from the draw path."""
        renderer = self._build_renderer()

        renderer.render(self.screen, build_snapshot(control_queue_depth=7))

        self.osd.set_control.assert_not_called()
        self.osd.update_control_queue.assert_not_called()
        self.osd.update_debug_status.assert_not_called()
        self.osd.update_buffer_queue.assert_not_called()

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_draws_menu_when_visible(self, _mock_flip):
        renderer = self._build_renderer()

        renderer.render(self.screen, build_snapshot(menu_visible=True))

        self.menu.draw.assert_called_once_with(self.screen)

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_skips_menu_when_hidden(self, _mock_flip):
        renderer = self._build_renderer()

        renderer.render(self.screen, build_snapshot(menu_visible=False))

        self.menu.draw.assert_not_called()

    @patch("v3xctrl_ui.core.Renderer.pygame.display.flip")
    def test_render_shows_connect_screen_before_the_user_connects(self, _mock_flip):
        renderer = self._build_renderer()

        with patch.object(renderer, "_render_connect_screen") as mock_connect:
            renderer.render(self.screen, build_snapshot(user_connected=False))

        mock_connect.assert_called_once()
        self.osd.render.assert_not_called()

    def test_set_connect_callback(self):
        renderer = self._build_renderer()
        callback = MagicMock()

        renderer.set_connect_callback(callback)
        renderer.connect_button.callback()

        callback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
