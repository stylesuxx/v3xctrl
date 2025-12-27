"""Event handling controller for pygame events."""
from typing import TYPE_CHECKING, Callable, Optional

import pygame

from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.utils.Commands import Commands
from v3xctrl_ui.utils.Settings import Settings

if TYPE_CHECKING:
    from v3xctrl_ui.menu.Menu import Menu


class EventController:
    def __init__(
        self,
        on_quit: Callable[[], None],
        on_toggle_fullscreen: Callable[[], None],
        create_menu: Callable[[], 'Menu'],
        on_menu_exit: Callable[[], None],
        send_command: Callable,
        settings: Settings,
        telemetry_context: TelemetryContext
    ):
        self.on_quit = on_quit
        self.on_toggle_fullscreen = on_toggle_fullscreen
        self.create_menu = create_menu
        self.on_menu_exit = on_menu_exit
        self.send_command = send_command
        self.settings = settings
        self.telemetry_context = telemetry_context
        self.menu: Optional['Menu'] = None

        self._load_keyboard_controls()

    def handle_events(self) -> bool:
        """Returns False if application should quit."""
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.on_quit()
                return False

            elif event.type == pygame.KEYDOWN:
                match event.key:
                    case pygame.K_ESCAPE:
                        # [ESC] - Toggle Menu
                        if self.menu is None:
                            self.menu = self.create_menu()
                        else:
                            if not self.menu.is_loading:
                                # When exiting via [ESC], do the same thing we would do
                                # when using the "Back" button from the menu
                                self.on_menu_exit()

                    case pygame.K_F11:
                        # [F11] - Toggle Fullscreen
                        self.on_toggle_fullscreen()

                    case _ if self.menu is None:
                        # Only process custom keyboard controls when not in menu
                        match event.key:
                            case self.trim_increase_key:
                                self.send_command(Commands.trim_increase(), lambda success: None)

                            case self.trim_decrease_key:
                                self.send_command(Commands.trim_decrease(), lambda success: None)

                            case self.rec_toggle_key:
                                if self.telemetry_context.get_gst().recording:
                                    self.send_command(Commands.recording_stop(), lambda success: None)
                                else:
                                    self.send_command(Commands.recording_start(), lambda success: None)

            if self.menu is not None:
                self.menu.handle_event(event)

        return True

    def clear_menu(self) -> None:
        self.menu = None

    def set_menu_tab_enabled(self, tab_name: str, enabled: bool) -> None:
        if self.menu:
            self.menu.set_tab_enabled(tab_name, enabled)

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        self._load_keyboard_controls()

    def _load_keyboard_controls(self) -> None:
        keyboard_controls = self.settings.get("controls", {}).get("keyboard", {})

        self.trim_increase_key = keyboard_controls.get("trim_increase")
        self.trim_decrease_key = keyboard_controls.get("trim_decrease")
        self.rec_toggle_key = keyboard_controls.get("rec_toggle")
