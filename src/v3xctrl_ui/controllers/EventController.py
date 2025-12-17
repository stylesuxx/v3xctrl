"""Event handling controller for pygame events."""
from typing import TYPE_CHECKING, Callable, Optional

import pygame

if TYPE_CHECKING:
    from v3xctrl_ui.menu.Menu import Menu


class EventController:
    def __init__(
        self,
        on_quit: Callable[[], None],
        on_toggle_fullscreen: Callable[[], None],
        create_menu: Callable[[], 'Menu'],
        on_menu_exit: Callable[[], None]
    ):
        self.on_quit = on_quit
        self.on_toggle_fullscreen = on_toggle_fullscreen
        self.create_menu = create_menu
        self.on_menu_exit = on_menu_exit
        self.menu: Optional['Menu'] = None

    def handle_events(self) -> bool:
        """Returns False if application should quit."""
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.on_quit()
                return False

            elif event.type == pygame.KEYDOWN:

                # [ESC] - Toggle Menu
                if event.key == pygame.K_ESCAPE:
                    if self.menu is None:
                        self.menu = self.create_menu()
                    else:
                        if not self.menu.is_loading:
                            # When exiting via [ESC], do the same thing we would do
                            # when using the "Back" button from the menu
                            self.on_menu_exit()

                # [F11] - Toggle Fullscreen
                elif event.key == pygame.K_F11:
                    self.on_toggle_fullscreen()

            if self.menu is not None:
                self.menu.handle_event(event)

        return True

    def clear_menu(self) -> None:
        self.menu = None

    def set_menu_tab_enabled(self, tab_name: str, enabled: bool) -> None:
        if self.menu:
            self.menu.set_tab_enabled(tab_name, enabled)
