import logging
import math
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
import pygame

if TYPE_CHECKING:
    from v3xctrl_ui.core.AppState import AppState
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.menu.input.Button import Button
from v3xctrl_ui.menu.Menu import Menu
from v3xctrl_ui.network.NetworkController import NetworkController
from v3xctrl_ui.utils.colors import BLACK, RED, WHITE
from v3xctrl_ui.utils.fonts import BOLD_MONO_FONT_24, BOLD_MONO_FONT_32, BOLD_MONO_FONT_48, TEXT_FONT
from v3xctrl_ui.utils.helpers import get_external_ip


class Renderer:
    """
    Rendering display content
    """

    def __init__(self, size: tuple[int, int], settings: Settings) -> None:
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

        # Connect screen button (created once, repositioned on render)
        self._connect_button = Button(
            label="CONNECT",
            font=BOLD_MONO_FONT_48,
            callback=lambda: None,
            width=300,
            height=90,
            border_radius=45,
        )

        # Splash logo (loaded lazily after display is initialized)
        self._splash_logo: pygame.Surface | None = None
        self._splash_logo_loaded = False

    @property
    def connect_button(self) -> Button:
        return self._connect_button

    def set_connect_callback(self, callback: Callable[[], None]) -> None:
        self._connect_button.callback = callback

    def render_all(
        self,
        state: "AppState",
        network_controller: NetworkController,
        fullscreen: bool = False,
        scale: float = 1.0,
    ) -> None:
        self.fullscreen = fullscreen
        self.scale = scale

        # Use screen surface size (not window size) to handle HiDPI scaling correctly
        screen_size = state.screen.get_size()
        self.center_x = screen_size[0] // 2
        self.center_y = screen_size[1] // 2

        if not state.model.user_connected:
            self._render_connect_screen(state.screen)
            self._render_menu(state.screen, state.menu)
            pygame.display.flip()
            return

        frame = self._get_video_frame(network_controller)

        if frame is not None:
            self._render_video_frame(state.screen, frame)
        else:
            self._render_no_video_signal_screen(state.screen, network_controller.relay_status_message)

            if not state.model.control_connected:
                self._render_no_control_signal_screen(state.screen)

            if network_controller.relay_enable:
                self._render_relay_status_screen(
                    network_controller.relay_status_message.upper(),
                    (self.center_x - 6, self.center_y - 110),
                    state.screen,
                )

        self._render_osd(state, network_controller)
        self._render_error_text(state.screen, network_controller)
        self._render_menu(state.screen, state.menu)

        pygame.display.flip()

    def _get_video_frame(self, network_manager: NetworkController) -> npt.NDArray[np.uint8] | None:
        """Get the current video frame if available."""
        if not network_manager.video_receiver:
            return None

        return network_manager.video_receiver.get_frame()

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

    def _render_text(
        self,
        screen: pygame.Surface,
        lines: list[tuple[str, str | None]],
        x: int,
        y: int,
    ):
        key_x = x
        base_y = y
        line_height = 36

        max_label_width = 0
        for i, (key, val) in enumerate(lines):
            y = base_y + i * line_height

            label = f"{key}"
            if val:
                label += ":"

            key_surf, key_rect = BOLD_MONO_FONT_24.render(label, WHITE)
            key_rect.topleft = (key_x, y)
            screen.blit(key_surf, key_rect)

            if val and key_rect.width > max_label_width:
                max_label_width = key_rect.width

        val_x = x + max_label_width + 15
        for i, (_key, val) in enumerate(lines):
            if val:
                y = base_y + i * line_height
                val_surf, val_rect = BOLD_MONO_FONT_24.render(val, WHITE)
                val_rect.topleft = (val_x, y)
                screen.blit(val_surf, val_rect)

    def _get_splash_logo(self) -> pygame.Surface | None:
        if not self._splash_logo_loaded:
            self._splash_logo_loaded = True
            base_path = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent.parent

            logo_path = base_path / "assets" / "images" / "v3xctrl_logo.png"
            try:
                self._splash_logo = pygame.image.load(str(logo_path)).convert_alpha()
            except Exception as e:
                logging.warning(f"Failed to load splash logo: {e}")
        return self._splash_logo

    def _render_connect_screen(self, screen: pygame.Surface) -> None:
        """Render splash screen with logo, connect button, and ESC hint."""
        screen.fill(BLACK)

        btn_w, btn_h = self._connect_button.get_size()
        spacing = 48

        # Scale logo to ~40% of screen width
        splash_logo = self._get_splash_logo()
        logo_h = 0
        if splash_logo is not None:
            target_w = int(screen.get_width() * 0.4)
            orig_w, orig_h = splash_logo.get_size()
            scale = target_w / orig_w
            target_h = int(orig_h * scale)
            logo = pygame.transform.smoothscale(splash_logo, (target_w, target_h))
            logo_h = target_h
        else:
            logo = None

        # Render hint text to measure it
        hint_surf, hint_rect = TEXT_FONT.render("Press [ESC] to enter the menu at any time", WHITE)

        # Calculate total height and starting y to center the group
        total_h = logo_h + spacing + btn_h + spacing + hint_rect.height
        start_y = self.center_y - total_h // 2
        y = start_y

        # Logo
        if logo is not None:
            screen.blit(logo, (self.center_x - logo.get_width() // 2, y))
            y += logo_h + spacing

        # Breathing glow behind connect button — bright at center, fades to black
        breath = math.sin(time.monotonic() * 2) * 0.5 + 0.5
        glow_expand = int(breath * 6)
        glow_pad = 50 + glow_expand
        glow_w = btn_w + glow_pad * 2
        glow_h = btn_h + glow_pad * 2
        glow_surf = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
        layers = 30
        for i in range(layers):
            t = (layers - 1 - i) / (layers - 1)
            w = int(btn_w + (glow_w - btn_w) * t)
            h = int(btn_h + (glow_h - btn_h) * t)
            alpha = int((1 - t) ** 4.5 * breath * 55)
            radius = min(w, h) // 2
            r = pygame.Rect((glow_w - w) // 2, (glow_h - h) // 2, w, h)
            pygame.draw.rect(glow_surf, (255, 255, 255, alpha), r, border_radius=radius)
        screen.blit(glow_surf, (self.center_x - glow_w // 2, y + btn_h // 2 - glow_h // 2))

        # Connect button
        self._connect_button.set_position(self.center_x - btn_w // 2, y)
        self._connect_button.draw(screen)
        y += btn_h + spacing

        # ESC hint
        screen.blit(hint_surf, (self.center_x - hint_rect.width // 2, y))

    def _render_no_control_signal_screen(self, screen: pygame.Surface) -> None:
        surface, rect = BOLD_MONO_FONT_32.render("NO CONTROL SIGNAL", RED)
        rect.center = (self.center_x - 6, self.center_y - 75)
        screen.blit(surface, rect)

    def _render_no_video_signal_screen(self, screen: pygame.Surface, relay_status_message: str) -> None:
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
        surface, rect = BOLD_MONO_FONT_32.render("NO VIDEO SIGNAL", RED)
        rect.center = (self.center_x, self.center_y - 40)
        screen.blit(surface, rect)

        show_connection_info = self.settings.get("show_connection_info", False)
        if show_connection_info:
            relay = self.settings.get("relay", {})
            if relay.get("enabled", False):
                self._render_relay_connection_info(screen)
            else:
                self._render_direct_connection_info(screen)

    def _render_relay_status_screen(self, msg: str, offset: tuple[int, int], screen: pygame.Surface) -> None:
        now = time.monotonic()
        breath = math.sin(now * 3) * 0.5 + 0.5
        alpha = int(50 + breath * 205)

        surface, rect = BOLD_MONO_FONT_32.render(msg, RED)
        surface.set_alpha(alpha)
        rect.center = offset
        screen.blit(surface, rect)

    def _render_relay_connection_info(self, screen: pygame.Surface) -> None:
        """Video and control ports are fixed with the relay."""
        ports = self.settings.get("ports")
        relay_settings = self.settings.get("relay")
        data: list[tuple[str, str | None]] = [
            ("STREAMER SETUP", None),
            ("Mode", "relay"),
            ("Relay Server", relay_settings.get("server")),
            ("Session ID", relay_settings.get("id")),
            ("", None),
            ("Network Ports", None),
            ("Video", str(ports["video"])),
            ("Control", str(ports["control"])),
        ]
        self._render_text(screen, data, 50, self.center_y + 10)

    def _render_direct_connection_info(self, screen: pygame.Surface) -> None:
        """Render IP and port information."""
        ports = self.settings.get("ports")
        data: list[tuple[str, str | None]] = [
            ("STREAMER SETUP", None),
            ("Mode", "direct"),
            ("Host", self.ip),
            ("", None),
            ("Network Ports", None),
            ("Video", str(ports["video"])),
            ("Control", str(ports["control"])),
        ]

        self._render_text(screen, data, 50, self.center_y + 10)

    def _render_error_text(self, screen: pygame.Surface, network_manager: "NetworkController") -> None:
        """Render error messages on top of main UI."""
        if network_manager.server_error:
            surface, rect = BOLD_MONO_FONT_24.render(network_manager.server_error, RED)
            rect.center = (self.center_x, 50)
            screen.blit(surface, rect)

    def _render_osd(self, state: "AppState", network_manager: NetworkController) -> None:
        """Render OSD and overlay information."""
        data_left = network_manager.get_data_queue_size()
        if network_manager.server_error:
            state.osd.update_debug_status("fail")

        state.osd.update_data_queue(data_left)
        state.osd.set_control(state.model.throttle, state.model.steering)

        video_history = None
        if network_manager.video_receiver is not None:
            video_history = network_manager.video_receiver.render_history.copy()

        state.osd.render(state.screen, state.model.loop_history.copy(), video_history)

    def _render_menu(self, screen: pygame.Surface, menu: Menu) -> None:
        """Render menu above everything else."""
        if menu.visible:
            menu.draw(screen)
