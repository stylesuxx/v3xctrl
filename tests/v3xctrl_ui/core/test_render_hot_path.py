"""Structural gate on the per-frame render path.

These assert invariants that keep frame latency where it is. They are call
counts and memory identity rather than wall times, so they hold on any machine
and in CI. Wall times come from benchmarks/render_frame.py.
"""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from collections import deque
from unittest.mock import MagicMock, patch

import numpy as np
import pygame

from tests.v3xctrl_ui.settings_helper import build_settings
from v3xctrl_ui.core.AppState import AppState
from v3xctrl_ui.core.MainThreadDispatcher import MainThreadDispatcher
from v3xctrl_ui.network.NetworkCoordinator import NetworkCoordinator

FRAME_COUNT = 5


class CountingReceiver:
    """Video receiver that records how often the render path pulls a frame."""

    def __init__(self) -> None:
        self.frame = np.zeros((600, 800, 3), dtype=np.uint8)
        self.render_history: deque[float] = deque([1.0, 2.0])
        self.frame_buffer: deque = deque()
        self.get_frame_calls = 0

    def get_frame(self) -> np.ndarray:
        self.get_frame_calls += 1
        # A real receiver hands out a different array as frames decode.
        self.frame = np.zeros((600, 800, 3), dtype=np.uint8)
        return self.frame


class CountingController:
    """Control channel that records how often the render path reads its depth."""

    def __init__(self, receiver: CountingReceiver) -> None:
        self.video_receiver = receiver
        self.server = None
        self.server_error = None
        self.relay_enable = False
        self.relay_status_message = ""
        self.relay_spectator_mode = False
        self.control_buffer_calls = 0

    def get_control_buffer_size(self) -> int:
        self.control_buffer_calls += 1
        return 3

    def get_video_frame(self):
        return self.video_receiver.get_frame()

    def get_video_history(self) -> deque[float]:
        return self.video_receiver.render_history.copy()

    def get_video_buffer_size(self) -> int:
        return len(self.video_receiver.frame_buffer)

    def has_recent_control_drops(self) -> bool:
        return False

    def has_recent_send_failures(self) -> bool:
        return False


@patch("v3xctrl_ui.core.AppState.Menu")
@patch("v3xctrl_ui.core.AppState.OSD")
@patch("v3xctrl_ui.core.AppState.InputController")
@patch("v3xctrl_ui.core.AppState.DisplayController")
class TestRenderHotPath(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.settings = build_settings(
            timing={"control_update_hz": 30, "latency_check_hz": 1, "main_loop_fps": 60},
            video={"width": 800, "height": 600, "fullscreen": False},
            ports={"video": 6666, "control": 6668},
        )

    def _build_app(self, mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls):
        screen = pygame.Surface((800, 600))
        mock_display = MagicMock()
        mock_display.get_screen.return_value = screen
        mock_display_cls.return_value = mock_display

        mock_menu_cls.return_value.visible = False

        with patch("v3xctrl_ui.core.AppState.pygame.time.Clock", return_value=MagicMock()):
            app = AppState(self.settings)

        receiver = CountingReceiver()
        controller = CountingController(receiver)

        coordinator = NetworkCoordinator(app.model, app.osd, self.settings, MainThreadDispatcher())
        coordinator.network_controller = controller
        app.network_coordinator = coordinator

        app.model.user_connected = True
        app.model.control_connected = True

        return app, receiver, controller, screen

    def test_frame_is_pulled_exactly_once_per_render(
        self, mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls
    ):
        """get_frame advances the receiver's buffer, so a second call drops a frame."""
        app, receiver, _controller, _screen = self._build_app(
            mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls
        )

        with patch("v3xctrl_ui.core.Renderer.pygame.display.flip"):
            for _ in range(FRAME_COUNT):
                app.render()

        self.assertEqual(receiver.get_frame_calls, FRAME_COUNT)

    def test_control_queue_depth_is_read_exactly_once_per_render(
        self, mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls
    ):
        app, _receiver, controller, _screen = self._build_app(
            mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls
        )

        with patch("v3xctrl_ui.core.Renderer.pygame.display.flip"):
            for _ in range(FRAME_COUNT):
                app.render()

        self.assertEqual(controller.control_buffer_calls, FRAME_COUNT)

    def test_frame_reaches_the_blit_without_being_copied(
        self, mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls
    ):
        """A copy of a 1280x720 frame costs megabytes of memcpy every frame."""
        app, receiver, _controller, _screen = self._build_app(
            mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls
        )

        with (
            patch("v3xctrl_ui.core.Renderer.pygame.display.flip"),
            patch("v3xctrl_ui.core.Renderer.pygame.surfarray.blit_array") as mock_blit,
        ):
            app.render()

        blitted = mock_blit.call_args[0][1]
        self.assertTrue(np.shares_memory(blitted, receiver.frame))

    def test_unchanged_frame_is_blitted_once(self, mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls):
        """The identity check skips redundant blits while no new frame decodes."""
        app, receiver, _controller, _screen = self._build_app(
            mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls
        )
        held_frame = receiver.frame
        receiver.get_frame = lambda: held_frame

        with (
            patch("v3xctrl_ui.core.Renderer.pygame.display.flip"),
            patch("v3xctrl_ui.core.Renderer.pygame.surfarray.blit_array") as mock_blit,
        ):
            for _ in range(FRAME_COUNT):
                app.render()

        self.assertEqual(mock_blit.call_count, 1)

    def test_no_frame_is_pulled_before_the_user_connects(
        self, mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls
    ):
        app, receiver, _controller, _screen = self._build_app(
            mock_display_cls, mock_input_cls, mock_osd_cls, mock_menu_cls
        )
        app.model.user_connected = False

        with patch("v3xctrl_ui.core.Renderer.pygame.display.flip"):
            app.render()

        self.assertEqual(receiver.get_frame_calls, 0)


if __name__ == "__main__":
    unittest.main()
