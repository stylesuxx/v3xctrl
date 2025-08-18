from typing import Optional, Tuple

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

    def render_all(
        self,
        state: 'AppState',
        network_manager: NetworkManager
    ) -> None:
        """Render the complete frame."""
        frame = self._get_video_frame(network_manager)

        if frame is not None:
            self._render_video_frame(state.screen, frame)
        else:
            self._render_no_signal(state.screen, network_manager.relay_status_message)

        self._render_overlay_data(state, network_manager)
        self._render_errors(state.screen, network_manager)
        self._render_menu(state.screen, state.menu)

        pygame.display.flip()

    def _get_video_frame(self, network_manager: 'NetworkManager') -> Optional[bytes]:
        """Get the current video frame if available."""
        if not network_manager.video_receiver:
            return None

        with network_manager.video_receiver.frame_lock:
            return network_manager.video_receiver.frame

    def _render_video_frame(self, screen: pygame.Surface, frame: bytes) -> None:
        """Render a video frame to the screen."""
        surface = pygame.image.frombuffer(frame.tobytes(), self.video_size, "RGB")
        screen.blit(surface, (0, 0))

    def _render_no_signal(self, screen: pygame.Surface, relay_status_message: str) -> None:
        """Render the no signal screen with connection info."""
        screen.fill(BLACK)

        # Main "No Signal" text
        surface, rect = BOLD_32_MONO_FONT.render("No Signal", RED)
        rect.center = (self.video_width // 2, self.video_height // 2 - 40)
        screen.blit(surface, rect)

        relay = self.settings.get("relay", {})
        if relay.get("enabled", False):
            # Show relay status
            surface, rect = BOLD_32_MONO_FONT.render(relay_status_message, RED)
            rect.center = (self.video_width // 2, self.video_height // 2 + 10)
            screen.blit(surface, rect)
        else:
            # Show connection info
            self._render_connection_info(screen)

    def _render_connection_info(self, screen: pygame.Surface) -> None:
        """Render IP and port information."""
        ports = self.settings.get("ports")
        info_data = [
            ("Host", self.ip),
            ("Video", str(ports['video'])),
            ("Control", str(ports['control'])),
        ]

        key_x = self.video_width // 2 - 140
        val_x = self.video_width // 2 - 10
        base_y = self.video_height // 2 + 10
        line_height = 36

        for i, (key, val) in enumerate(info_data):
            y = base_y + i * line_height
            key_surf, key_rect = BOLD_24_MONO_FONT.render(f"{key}:", WHITE)
            key_rect.topleft = (key_x, y)
            screen.blit(key_surf, key_rect)

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

        loop_history = state.loop_history.copy()
        video_history = None
        if network_manager.video_receiver is not None:
            video_history = network_manager.video_receiver.history.copy()

        state.osd.render(state.screen, loop_history, video_history)

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
