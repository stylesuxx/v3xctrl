from typing import Dict, Tuple

import pygame

from v3xctrl_ui.GamepadManager import GamepadManager
from v3xctrl_ui.KeyAxisHandler import KeyAxisHandler
from v3xctrl_ui.Settings import Settings


class InputManager:
    """Manages keyboard and gamepad input handling."""
    THROTTLE_RANGE = (-1.0, 1.0)
    STEERING_RANGE = (-1.0, 1.0)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.gamepad_manager = GamepadManager()
        self.key_handlers: Dict[str, KeyAxisHandler] = {}

        self._setup_gamepad_manager()
        self._setup_key_handlers()

    def read_inputs(self) -> Tuple[float, float]:
        """Read current input values. Returns (throttle, steering)."""
        pressed_keys = pygame.key.get_pressed()
        gamepad_inputs = self.gamepad_manager.read_inputs()

        # Start with keyboard inputs
        throttle = self.key_handlers["throttle"].update(pressed_keys)
        steering = self.key_handlers["steering"].update(pressed_keys)

        # Override with gamepad if available
        if gamepad_inputs:
            steering = gamepad_inputs["steering"]
            throttle_input = gamepad_inputs["throttle"]
            brake_input = gamepad_inputs["brake"]
            throttle = throttle_input - brake_input

        return throttle, steering

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings

        self._configure_gamepad_manager()
        self._setup_key_handlers()

    def shutdown(self) -> None:
        self.gamepad_manager.stop()

    def _setup_gamepad_manager(self) -> None:
        self._configure_gamepad_manager()
        self.gamepad_manager.start()

    def _configure_gamepad_manager(self) -> None:
        calibrations = self.settings.get("calibrations", {})
        for guid, calibration in calibrations.items():
            self.gamepad_manager.set_calibration(guid, calibration)

        input_settings = self.settings.get("input", {})
        if "guid" in input_settings:
            self.gamepad_manager.set_active(input_settings["guid"])

    def _setup_key_handlers(self) -> None:
        control_settings = self.settings.get("controls", {}).get("keyboard")
        if control_settings:
            self.key_handlers = {
                "throttle": KeyAxisHandler(
                    positive=control_settings["throttle_up"],
                    negative=control_settings["throttle_down"],
                    min_val=self.THROTTLE_RANGE[0],
                    max_val=self.THROTTLE_RANGE[1]
                ),
                "steering": KeyAxisHandler(
                    positive=control_settings["steering_right"],
                    negative=control_settings["steering_left"],
                    min_val=self.STEERING_RANGE[0],
                    max_val=self.STEERING_RANGE[1]
                )
            }
