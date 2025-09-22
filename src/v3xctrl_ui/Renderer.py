from typing import Optional, Tuple, List

import numpy as np
import numpy.typing as npt
import pygame

#from v3xctrl_ui.AppState import AppState
from v3xctrl_ui.colors import BLACK, RED, WHITE
from v3xctrl_ui.fonts import BOLD_24_MONO_FONT, BOLD_32_MONO_FONT
from v3xctrl_ui.helpers import get_external_ip
from v3xctrl_ui.menu.Menu import Menu
from v3xctrl_ui.Settings import Settings
from v3xctrl_ui.NetworkManager import NetworkManager


class Renderer:
    def __init__(self, size: Tuple[int, int], settings: Settings) -> None:
        self.video_width = size[0]
        self.video_height = size[1]
        self.video_size = size
        self.settings = settings

        self.ip = get_external_ip()
        self.video_surface = pygame.Surface(self.video_size)
        self.last_frame_id = None

        self.fullscreen = False
        self.scale = 1.0
        self.center_x = 0
        self.center_y = 0

    def render_all(
        self,
        state: 'AppState',
        network_manager: NetworkManager,
        fullscreen: bool = False,
        scale: float = 1.0,
    ) -> None:
        self.fullscreen = fullscreen
        self.scale = scale

        self.center_x = pygame.display.get_window_size()[0] // 2
        self.center_y = pygame.display.get_window_size()[1] // 2

        frame = self._get_video_frame(network_manager)
        if frame is not None:
            self._render_video_frame(state.screen, frame)
        else:
            self._render_no_video_signal(state.screen, network_manager.relay_status_message)

            if not state.control_connected:
                self._render_no_control_signal(state.screen)

        self._render_overlay_data(state, network_manager)
        self._render_errors(state.screen, network_manager)
        self._render_menu(state.screen, state.menu)

        pygame.display.flip()

    def _get_video_frame(self, network_manager: NetworkManager) -> Optional[npt.NDArray[np.uint8]]:
        """Get the current video frame if available."""
        if not network_manager.video_receiver:
            return None

        with network_manager.video_receiver.frame_lock:
            return network_manager.video_receiver.frame

    def _render_video_frame(self, screen: pygame.Surface, frame: bytes) -> None:
        """Render a video frame to the screen."""
        current_frame_id = id(frame)
        if current_frame_id != self.last_frame_id:
            pygame.surfarray.blit_array(self.video_surface, frame.swapaxes(0, 1))
            self.last_frame_id = current_frame_id

        x, y = (0, 0)
        surface = self.video_surface

        if self.fullscreen:
            screen.fill((0, 0, 0))
            original_size = self.video_surface.get_size()
            width = int(original_size[0] * self.scale)
            height = int(original_size[1] * self.scale)

            surface = pygame.transform.scale(surface, (width, height))

            # Calculate position to center the scaled video
            x = self.center_x - width // 2
            y = self.center_y - height // 2

        screen.blit(surface, (x, y))

    def _render_no_control_signal(self, screen: pygame.Surface) -> None:
        surface, rect = BOLD_32_MONO_FONT.render("No Control Signal", RED)
        rect.center = (self.center_x - 6, self.center_y - 70)
        screen.blit(surface, rect)

    def _render_no_video_signal(self, screen: pygame.Surface, relay_status_message: str) -> None:
        """
        Render connection information depending on connection and signal states

        Technically we can be in one of 2 connection states:
        * direct
        * relay

        Ans in one of four signal states:
        * Control and Video missing
        * Control missing
        * Video missing
        * Fully connected
        """
        screen.fill(BLACK)

        # Main "No Signal" text
        surface, rect = BOLD_32_MONO_FONT.render("No Video Signal", RED)
        rect.center = (self.center_x, self.center_y - 40)
        screen.blit(surface, rect)

        show_connection_info = self.settings.get("show_connection_info", False)
        if show_connection_info:
            relay = self.settings.get("relay", {})
            if relay.get("enabled", False):
                self._render_relay_connection_info(screen)
            else:
                self._render_direct_connection_info(screen)

    def _render_relay_connection_info(self, screen: pygame.Surface) -> None:
        """Video and control ports are fixed with the relay."""
        relay_settings = self.settings.get("relay")
        data: List[Tuple[str, Optional[str]]] = [
            ("STREAMER SETUP", None),
            ("Mode", "relay"),
            ("Relay Server", relay_settings.get("server")),
            ("Session ID", relay_settings.get("id")),

            ("", None),
            ("Network Ports", None),
            ("Video", "6666"),
            ("Control", "6668"),
        ]
        self._render_lines(screen, data, 50, self.center_y + 10)

    def _render_direct_connection_info(self, screen: pygame.Surface) -> None:
        """Render IP and port information."""
        ports = self.settings.get("ports")
        data: List[Tuple[str, Optional[str]]] = [
            ("STREAMER SETUP", None),
            ("Mode", "direct"),
            ("Host", self.ip),

            ("", None),
            ("Network Ports", None),
            ("Video", str(ports['video'])),
            ("Control", str(ports['control'])),
        ]

        self._render_lines(screen, data, 50, self.center_y + 10)

    def _render_lines(
        self,
        screen: pygame.Surface,
        data: List[Tuple[str, Optional[str]]],
        x: int,
        y: int,
    ):
        key_x = x
        base_y = y
        line_height = 36

        max_label_width = 0
        for i, (key, val) in enumerate(data):
            y = base_y + i * line_height

            label = f"{key}"
            if val:
                label += ":"

            key_surf, key_rect = BOLD_24_MONO_FONT.render(label, WHITE)
            key_rect.topleft = (key_x, y)
            screen.blit(key_surf, key_rect)

            if val and key_rect.width > max_label_width:
                max_label_width = key_rect.width

        val_x = x + max_label_width + 15
        for i, (key, val) in enumerate(data):
            if val:
                y = base_y + i * line_height
                val_surf, val_rect = BOLD_24_MONO_FONT.render(val, WHITE)
                val_rect.topleft = (val_x, y)
                screen.blit(val_surf, val_rect)

    def _render_overlay_data(
        self,
        state: 'AppState',
        network_manager: NetworkManager
    ) -> None:
        """Render OSD and overlay information."""
        data_left = network_manager.get_data_queue_size()
        if network_manager.server_error:
            state.osd.update_debug_status("fail")

        state.osd.update_data_queue(data_left)
        state.osd.set_control(state.throttle, state.steering)

        video_history = None
        if network_manager.video_receiver is not None:
            video_history = network_manager.video_receiver.history.copy()

        state.osd.render(
            state.screen,
            state.loop_history.copy(),
            video_history
        )

    def _render_errors(self, screen: pygame.Surface, network_manager: 'NetworkManager') -> None:
        """Render error messages on top of main UI."""
        if network_manager.server_error:
            surface, rect = BOLD_24_MONO_FONT.render(network_manager.server_error, RED)
            rect.center = (self.video_width // 2, 50)
            screen.blit(surface, rect)

    def _render_menu(self, screen: pygame.Surface, menu: Optional['Menu']) -> None:
        """Render menu above everything else."""
        if menu is not None:
            menu.draw(screen)
