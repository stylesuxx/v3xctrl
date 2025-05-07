import pygame
from pygame import Surface
from typing import Callable

from ui.GamepadManager import GamepadManager
from ui.Settings import Settings

from ui.menu.Button import Button
from ui.menu.tabs import GeneralTab, InputTab, VideoTab

from ui.colors import WHITE, GREY, MID_GREY, DARK_GREY
from ui.fonts import MAIN_FONT


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

        self.tabs = ["General", "Frequencies", "Input"]
        self.active_tab = self.tabs[0]
        self.disable_tabs = False

        self.tab_height = 60
        self.footer_height = 60
        self.padding = 20

        save_button_x = self.width - 240
        exit_button_x = self.width - 120

        button_width = 100
        button_height = 40

        button_y = self.height - self.footer_height

        self.tab_rects = self._generate_tab_rects()

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

        self.tab_views = {
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
            "Frequencies": VideoTab(
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

    def _save_button_callback(self):
        settings = self.tab_views[self.active_tab].get_settings()

        for key, val in settings.items():
            self.settings.set(key, val)

        self.settings.save()

    def _exit_button_callback(self):
        self.active_tab = self.tabs[0]
        self.callback()

    def _generate_tab_rects(self):
        tab_width = self.width // len(self.tabs)
        return {
            name: pygame.Rect(i * tab_width, 0, tab_width, self.tab_height)
            for i, name in enumerate(self.tabs)
        }

    def handle_event(self, event):
        self.save_button.handle_event(event)
        self.exit_button.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.disable_tabs:
                for tab, rect in self.tab_rects.items():
                    if rect.collidepoint(event.pos):
                        self.active_tab = tab

        self.tab_views[self.active_tab].handle_event(event)

    def draw(self, surface: Surface):
        surface.blit(self.background, (0, 0))

        for i, (tab, rect) in enumerate(self.tab_rects.items()):
            color = self.TAB_ACTIVE_COLOR if tab == self.active_tab else self.TAB_INACTIVE_COLOR
            pygame.draw.rect(surface, color, rect)
            if i > 0:
                pygame.draw.line(surface, self.TAB_SEPARATOR_COLOR, rect.topleft, rect.bottomleft, 2)
            label_surface, label_rect = MAIN_FONT.render(tab, self.FONT_COLOR)
            label_rect.center = rect.center
            surface.blit(label_surface, label_rect)

        self.save_button.draw(surface)
        self.exit_button.draw(surface)

        self.tab_views[self.active_tab].draw(surface)
