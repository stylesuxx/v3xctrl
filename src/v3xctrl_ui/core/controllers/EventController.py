"""Event handling controller for pygame events."""
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import pygame

from v3xctrl_ui.core.controllers.input.GamepadController import GamepadController
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.menu.input.Button import Button
from v3xctrl_ui.menu.Menu import Menu
from v3xctrl_ui.network.Commands import Commands

if TYPE_CHECKING:
    from v3xctrl_ui.core.dataclasses import ApplicationModel


class EventController:
    def __init__(
        self,
        on_quit: Callable[[], None],
        on_toggle_fullscreen: Callable[[], None],
        menu: Menu,
        on_menu_exit: Callable[[], None],
        send_command: Callable,
        settings: Settings,
        telemetry_context: TelemetryContext,
        gamepad_controller: GamepadController | None = None,
        connect_button: Button | None = None,
        model: 'ApplicationModel | None' = None,
    ):
        self.on_quit = on_quit
        self.on_toggle_fullscreen = on_toggle_fullscreen
        self.menu = menu
        self.on_menu_exit = on_menu_exit
        self.send_command = send_command
        self.settings = settings
        self.telemetry_context = telemetry_context
        self.gamepad_controller = gamepad_controller
        self.connect_button = connect_button
        self.model = model

        self._load_keyboard_controls()

    def handle_events(self) -> bool:
        """Returns False if application should quit."""
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.on_quit()
                return False

            elif event.type == pygame.KEYUP:
                match event.key:
                    case pygame.K_ESCAPE:
                        # [ESC] - Toggle Menu
                        if not self.menu.visible:
                            self.menu.show()
                        elif not self.menu.is_loading:
                            # When exiting via [ESC], do the same thing we would do
                            # when using the "Back" button from the menu
                            self.settings.load()
                            self.on_menu_exit()

                    case pygame.K_F11:
                        # [F11] - Toggle Fullscreen
                        self.on_toggle_fullscreen()

                    case _ if not self.menu.visible and self._is_connected():
                        # Only process custom keyboard controls when connected and not in menu
                        match event.key:
                            case self.trim_increase_key:
                                self.send_command(Commands.trim_increase(), self._on_command_ack)

                            case self.trim_decrease_key:
                                self.send_command(Commands.trim_decrease(), self._on_command_ack)

                            case self.rec_toggle_key:
                                if self.telemetry_context.get_gst().recording:
                                    self.send_command(Commands.recording_stop(), self._on_command_ack)
                                else:
                                    self.send_command(Commands.recording_start(), self._on_command_ack)

            elif not self.menu.visible and self._is_connected() and self.gamepad_controller:
                action = self._match_gamepad_mapping(event)
                if action == "trim_increase":
                    self.send_command(Commands.trim_increase(), self._on_command_ack)
                elif action == "trim_decrease":
                    self.send_command(Commands.trim_decrease(), self._on_command_ack)
                elif action == "rec_toggle":
                    if self.telemetry_context.get_gst().recording:
                        self.send_command(Commands.recording_stop(), self._on_command_ack)
                    else:
                        self.send_command(Commands.recording_start(), self._on_command_ack)

            # Route events to connect button when on connect screen
            if (
                self.connect_button is not None
                and not self._is_connected()
                and not self.menu.visible
            ):
                self.connect_button.handle_event(event)

                if event.type == pygame.MOUSEMOTION:
                    if self.connect_button.hovered:
                        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                    else:
                        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

            if self.menu.visible:
                self.menu.handle_event(event)

        return True

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        self._load_keyboard_controls()

    def set_menu_tab_enabled(self, tab_name: str, enabled: bool) -> None:
        self.menu.set_tab_enabled(tab_name, enabled)

    def _on_command_ack(self, success: bool) -> None:
        logging.info(f"Received command ack: {success}")

    def _is_connected(self) -> bool:
        return self.model is not None and self.model.user_connected

    def _match_gamepad_mapping(self, event: pygame.event.Event) -> str | None:
        """Check if a pygame event matches any gamepad button/hat mapping."""
        for name in ("trim_increase", "trim_decrease", "rec_toggle"):
            mapping = self.gamepad_controller.get_button_mapping(name)
            if mapping is None:
                continue

            if isinstance(mapping, int) and event.type == pygame.JOYBUTTONUP:
                if event.button == mapping:
                    return name

            elif isinstance(mapping, dict) and event.type == pygame.JOYHATMOTION:
                if event.hat == mapping["hat"] and list(event.value) == mapping["value"]:
                    return name

        return None

    def _load_keyboard_controls(self) -> None:
        keyboard_controls = self.settings.get("controls", {}).get("keyboard", {})

        self.trim_increase_key = keyboard_controls.get("trim_increase")
        self.trim_decrease_key = keyboard_controls.get("trim_decrease")
        self.rec_toggle_key = keyboard_controls.get("rec_toggle")
