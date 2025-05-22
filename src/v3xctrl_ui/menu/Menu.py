from collections import namedtuple
import pygame
from pygame import Surface
from typing import Callable

from v3xctrl_ui.GamepadManager import GamepadManager
from v3xctrl_ui.Settings import Settings

from v3xctrl_ui.menu.Button import Button
from v3xctrl_ui.menu.tabs import GeneralTab, InputTab, FrequenciesTab

from v3xctrl_ui.colors import WHITE, GREY, MID_GREY, DARK_GREY
from v3xctrl_ui.fonts import MAIN_FONT

TabEntry = namedtuple("TabEntry", ["name", "rect", "view"])


class Menu:
    BG_COLOR = DARK_GREY
    TAB_ACTIVE_COLOR = MID_GREY
    TAB_INACTIVE_COLOR = GREY
    TAB_SEPARATOR_COLOR = BG_COLOR
    FONT_COLOR = WHITE

    def __init__(self,
                 width: int,
                 height: int,
                 gamepad_manager: GamepadManager,
                 settings: Settings,
                 callback: Callable[[], None]):
        self.width = width
        self.height = height
        self.gamepad_manager = gamepad_manager
        self.settings = settings
        self.callback = callback

        tab_width = self.width // 3
        tab_names = ["General", "Frequencies", "Input"]

        self.tab_height = 60
        self.footer_height = 60
        self.padding = 20

        button_width = 100
        button_height = 40

        tab_views = self._create_tabs()

        self.tabs = []
        for i, name in enumerate(tab_names):
            rect = pygame.Rect(i * tab_width, 0, tab_width, self.tab_height)
            view = tab_views[name]
            self.tabs.append(TabEntry(name, rect, view))

        self.active_tab = self.tabs[0].name
        self.disable_tabs = False

        save_button_x = self.width - (button_width + self.padding) * 2
        exit_button_x = self.width - button_width - self.padding

        button_y = self.height - self.footer_height

        self.save_button = Button(
            "Save",
            button_width, button_height,
            MAIN_FONT,
            self._save_button_callback)

        self.exit_button = Button(
            "Back",
            button_width, button_height,
            MAIN_FONT,
            self._exit_button_callback)

        self.save_button.set_position(save_button_x, button_y)
        self.exit_button.set_position(exit_button_x, button_y)

        self.background = pygame.Surface((self.width, self.height))
        self.background.fill(self.BG_COLOR)

    def _create_tabs(self) -> dict:
        return {
            "General": GeneralTab(
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
        }

    def _on_active_toggle(self, active: bool):
        if active:
            self.disable_tabs = True
            self.save_button.disable()
            self.exit_button.disable()
        else:
            self.disable_tabs = False
            self.save_button.enable()
            self.exit_button.enable()

    def _get_active_tab(self) -> TabEntry:
        return next((t for t in self.tabs if t.name == self.active_tab), None)

    def _save_button_callback(self):
        tab = self._get_active_tab()
        if tab:
            settings = tab.view.get_settings()

            for key, val in settings.items():
                self.settings.set(key, val)

            self.settings.save()

    def _exit_button_callback(self):
        self.active_tab = self.tabs[0].name
        self.callback()

    def _draw_tabs(self, surface: Surface):
        for i, entry in enumerate(self.tabs):
            color = self.TAB_ACTIVE_COLOR if entry.name == self.active_tab else self.TAB_INACTIVE_COLOR
            pygame.draw.rect(surface, color, entry.rect)
            if i > 0:
                pygame.draw.line(surface, self.TAB_SEPARATOR_COLOR, entry.rect.topleft, entry.rect.bottomleft, 2)
            label_surface, label_rect = MAIN_FONT.render(entry.name, self.FONT_COLOR)
            label_rect.center = entry.rect.center
            surface.blit(label_surface, label_rect)

    def handle_event(self, event):
        self.save_button.handle_event(event)
        self.exit_button.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.disable_tabs:
                for entry in self.tabs:
                    if entry.rect.collidepoint(event.pos):
                        self.active_tab = entry.name

        tab = self._get_active_tab()
        if tab:
            tab.view.handle_event(event)

    def draw(self, surface: Surface):
        surface.blit(self.background, (0, 0))
        self._draw_tabs(surface)
        self.save_button.draw(surface)
        self.exit_button.draw(surface)

        tab = self._get_active_tab()
        if tab:
            tab.view.draw(surface)
