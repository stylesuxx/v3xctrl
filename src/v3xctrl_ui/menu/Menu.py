import math
import time

import pygame
from pygame import Surface, event
from typing import Callable, NamedTuple, Dict

from v3xctrl_control.message import Command

from v3xctrl_ui.colors import WHITE, DARK_GREY, CHARCOAL, GREY, TRANSPARENT_BLACK
from v3xctrl_ui.fonts import MAIN_FONT
from v3xctrl_ui.i18n import t
from v3xctrl_ui.GamepadManager import GamepadManager
from v3xctrl_ui.Settings import Settings
from v3xctrl_ui.menu.input import Button
from v3xctrl_ui.menu.tabs import (
  GeneralTab,
  InputTab,
  FrequenciesTab,
  StreamerTab,
  OsdTab,
  NetworkTab,
  Tab
)


class TabEntry(NamedTuple):
    name: str
    rect: pygame.Rect
    view: NamedTuple
    enabled: bool = True


class Menu:
    BG_COLOR = DARK_GREY
    TAB_ACTIVE_COLOR = DARK_GREY
    TAB_INACTIVE_COLOR = CHARCOAL
    TAB_SEPARATOR_COLOR = BG_COLOR
    FONT_COLOR = WHITE
    FONT_COLOR_INACTIVE = GREY
    LOADING_OVERLAY_COLOR = TRANSPARENT_BLACK

    def __init__(
        self,
        width: int,
        height: int,
        gamepad_manager: GamepadManager,
        settings: Settings,
        invoke_command: Callable[[Command, Callable[[bool], None]], None],
        callback: Callable[[], None],
        callback_quit: Callable[[], None],
    ) -> None:
        self.width = width
        self.height = height
        self.gamepad_manager = gamepad_manager
        self.settings = settings
        self.invoke_command = invoke_command

        self.callback = callback
        self.callback_quit = callback_quit

        tab_names = [
            t("General"),
            t("Input"),
            t("OSD"),
            t("Network"),
            t("Streamer"),
            t("Frequencies"),
        ]
        tab_width = self.width // len(tab_names)

        self.tab_height = 60
        self.footer_height = 60
        self.padding = 20

        tab_views = self._create_tabs()

        self.tabs = []
        for i, name in enumerate(tab_names):
            rect = pygame.Rect(i * tab_width, 0, tab_width, self.tab_height)
            view = tab_views[name]
            self.tabs.append(TabEntry(name, rect, view))

        self.active_tab = self.tabs[0].name
        self.disable_tabs = False

        # Buttons
        self.quit_button = Button(t("Quit"), MAIN_FONT, self._quit_button_callback)
        self.save_button = Button(t("Save"), MAIN_FONT, self._save_button_callback)
        self.exit_button = Button(t("Back"), MAIN_FONT, self._exit_button_callback)

        # Button positions
        button_y = self.height - self.quit_button.height - self.padding

        quit_button_x = self.padding
        exit_button_x = self.width - self.exit_button.width - self.padding
        save_button_x = exit_button_x - self.save_button.width - self.padding

        self.quit_button.set_position(quit_button_x, button_y)
        self.save_button.set_position(save_button_x, button_y)
        self.exit_button.set_position(exit_button_x, button_y)

        self.background = pygame.Surface((self.width, self.height))
        self.background.fill(self.BG_COLOR)

        self.tab_bar_dirty = True
        self.tab_bar_surface = pygame.Surface((self.width, self.tab_height))

        # Loading screen
        self.is_loading = False
        self.loading_text = "Applying settings!"
        self.loading_result_time = 1.2

        self.spinner_angle = 0
        self.spinner_radius = 30
        self.spinner_thickness = 4
        self.spinner_offset = 60

    def handle_event(self, event: event.Event) -> None:
        # Events can be ignored if loading screen is shown
        if self.is_loading:
            return

        self.quit_button.handle_event(event)
        self.save_button.handle_event(event)
        self.exit_button.handle_event(event)

        # Pass event to tabbar
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.disable_tabs:
                for entry in self.tabs:
                    if entry.rect.collidepoint(event.pos) and entry.enabled:
                        self.active_tab = entry.name
                        self.tab_bar_dirty = True

        # Pass event to active tab
        tab = self._get_active_tab()
        if tab:
            tab.view.handle_event(event)

    def draw(self, surface: Surface) -> None:
        surface.blit(self.background, (0, 0))

        if self.tab_bar_dirty:
            self._render_tabs()
            self.tab_bar_dirty = False

        surface.blit(self.tab_bar_surface, (0, 0))
        self._draw_buttons(surface)

        tab = self._get_active_tab()
        if tab:
            tab.view.draw(surface)

        if self.is_loading:
            self._draw_loading_overlay(surface)
            self.spinner_angle = (self.spinner_angle + 5) % 360

    def set_tab_enabled(self, tab_name: str, enabled: bool) -> None:
        for i, entry in enumerate(self.tabs):
            if entry.name == tab_name:
                self.tabs[i] = entry._replace(enabled=enabled)

                if self.active_tab == tab_name:
                    self.active_tab = self.tabs[0].name

                self.tab_bar_dirty = True
                break

    def show_loading(self, text: str = t("Applying settings!")) -> None:
        self.is_loading = True
        self.loading_text = text

    def _create_tabs(self) -> Dict[str, Tab]:
        return {
            "General": GeneralTab(
                settings=self.settings,
                width=self.width,
                height=self.height,
                padding=self.padding,
                y_offset=self.tab_height
            ),
            "OSD": OsdTab(
                settings=self.settings,
                width=self.width,
                height=self.height,
                padding=self.padding,
                y_offset=self.tab_height
            ),
            "Input": InputTab(
                settings=self.settings,
                width=self.width,
                height=self.height,
                padding=self.padding,
                y_offset=self.tab_height,
                gamepad_manager=self.gamepad_manager,
                on_active_toggle=self._on_active_toggle
            ),
            "Frequencies": FrequenciesTab(
                settings=self.settings,
                width=self.width,
                height=self.height,
                padding=self.padding,
                y_offset=self.tab_height
            ),
            "Streamer": StreamerTab(
                settings=self.settings,
                width=self.width,
                height=self.height,
                padding=self.padding,
                y_offset=self.tab_height,
                on_active_toggle=self._on_active_toggle,
                send_command=self._on_send_command,
            ),
            "Network": NetworkTab(
                settings=self.settings,
                width=self.width,
                height=self.height,
                padding=self.padding,
                y_offset=self.tab_height
            ),
        }

    def _on_send_command(self, command: Command, callback: Callable[[bool], None]) -> None:
        # Wrap callback so we can handle loading screen updates
        def callback_wrapper(state: bool = False) -> None:
            # Show success or Fail message
            result = t("Success!")
            if not state:
                result = t("Failed!")

            self.show_loading(result)
            countdown = 0
            while countdown < self.loading_result_time:
                countdown += 0.1
                time.sleep(0.1)

            self.is_loading = False
            callback(state)

        self.invoke_command(command, callback_wrapper)

    def _on_active_toggle(self, active: bool) -> None:
        if active:
            self.disable_tabs = True
            self.save_button.disable()
            self.exit_button.disable()
            self.quit_button.disable()
        else:
            self.disable_tabs = False
            self.save_button.enable()
            self.exit_button.enable()
            self.quit_button.enable()

    def _get_active_tab(self) -> TabEntry:
        return next((t for t in self.tabs if t.name == self.active_tab), None)

    def _save_button_callback(self) -> None:
        tab = self._get_active_tab()
        if tab:
            settings = tab.view.get_settings()
            for key, val in settings.items():
                self.settings.set(key, val)
            self.settings.save()

    def _exit_button_callback(self) -> None:
        self.active_tab = self.tabs[0].name
        self.callback()

    def _quit_button_callback(self) -> None:
        self.callback_quit()

    def _render_tabs(self) -> None:
        """Render the tab bar to the cached surface"""
        for i, entry in enumerate(self.tabs):
            is_active = entry.name == self.active_tab

            color = self.TAB_ACTIVE_COLOR if is_active else self.TAB_INACTIVE_COLOR
            font_color = self.FONT_COLOR
            if not entry.enabled:
                color = self.TAB_INACTIVE_COLOR
                font_color = self.FONT_COLOR_INACTIVE

            # Draw directly to the cached tab_bar_surface
            pygame.draw.rect(self.tab_bar_surface, color, entry.rect)

            # Draw left border
            if i > 0:
                pygame.draw.line(
                    self.tab_bar_surface,
                    self.TAB_SEPARATOR_COLOR,
                    entry.rect.topleft,
                    entry.rect.bottomleft,
                    2
                )

            # Render text
            label_surface, label_rect = MAIN_FONT.render(entry.name, font_color)
            label_rect.center = entry.rect.center
            self.tab_bar_surface.blit(label_surface, label_rect)

    def _draw_buttons(self, surface: Surface) -> None:
        self.quit_button.draw(surface)
        self.save_button.draw(surface)
        self.exit_button.draw(surface)

    def _draw_loading_overlay(self, surface: Surface) -> None:
        """Draw semi-transparent overlay with loading spinner and text"""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill(self.LOADING_OVERLAY_COLOR)
        surface.blit(overlay, (0, 0))

        center_x = self.width // 2
        center_y = self.height // 2

        # Draw spinning arc
        # Draw multiple arcs to create a smooth spinner effect
        num_segments = 8

        for i in range(num_segments):
            # Calculate opacity for each segment (fade effect)
            segment_angle = (self.spinner_angle + i * (360 / num_segments)) % 360
            alpha = int(255 * (i / num_segments))

            # Calculate start and end points for this segment
            angle_rad = math.radians(segment_angle)
            x = center_x + int(self.spinner_radius * math.cos(angle_rad))
            y = center_y + int(self.spinner_radius * math.sin(angle_rad))

            # Draw small circle for each segment
            color = (*WHITE[:3], alpha) if len(WHITE) == 3 else (WHITE[0], WHITE[1], WHITE[2], alpha)
            pygame.draw.circle(surface, color, (x, y), self.spinner_thickness)

        # Render loading text below the spinner
        text_surface, text_rect = MAIN_FONT.render(self.loading_text, WHITE)
        text_rect.center = (center_x, center_y + self.spinner_offset)
        surface.blit(text_surface, text_rect)
