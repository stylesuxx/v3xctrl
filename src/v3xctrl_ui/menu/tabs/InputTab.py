from typing import Callable, Dict, List, Any

from pygame import Surface

from v3xctrl_ui.fonts import LABEL_FONT
from v3xctrl_ui.i18n import t
from v3xctrl_ui.GamepadManager import GamepadManager
from v3xctrl_ui.menu.calibration.GamepadCalibrationWidget import (
  GamepadCalibrationWidget
)
from v3xctrl_ui.menu.input import KeyMappingWidget
from v3xctrl_ui.Settings import Settings

from .Tab import Tab
from .VerticalLayout import VerticalLayout


class InputTab(Tab):
    def __init__(
        self,
        settings: Settings,
        width: int,
        height: int,
        padding: int,
        y_offset: int,
        gamepad_manager: GamepadManager,
        on_active_toggle: Callable[[bool], None]
    ) -> None:
        super().__init__(settings, width, height, padding, y_offset)

        self.on_active_toggle = on_active_toggle
        self.gamepad_manager = gamepad_manager

        self.key_widgets: List[KeyMappingWidget] = []
        keyboard_controls = self.settings.get("controls", {}).get("keyboard", {})

        for name, key in keyboard_controls.items():
            widget = KeyMappingWidget(
                control_name=name,
                key_code=key,
                font=LABEL_FONT,
                on_key_change=(
                    lambda new_key,
                    name=name: self._on_control_key_change(name, new_key)
                ),
                on_remap_toggle=self._on_active_toggle
            )
            self.key_widgets.append(widget)

        self.calibration_widget = GamepadCalibrationWidget(
            font=LABEL_FONT,
            manager=self.gamepad_manager,
            on_calibration_start=self._on_calibration_start,
            on_calibration_done=self._on_calibration_done
        )

        self.elements = self.key_widgets + [self.calibration_widget]

        self.headline_surfaces = {
            "keyboard": self._create_headline(t("Keyboard")),
            "input": self._create_headline(t("Input device"), True)
        }

        self.keyboard_layout = VerticalLayout()
        for element in self.key_widgets:
            self.keyboard_layout.add(element)

        self.input_layout = VerticalLayout()
        self.input_layout.add(self.calibration_widget)

    def draw(self, surface: Surface) -> None:
        y = self._draw_keyboard_section(surface, 0)
        y = self._draw_input_section(surface, y)

    def get_settings(self) -> Dict[str, Any]:
        return {
            "input": {
                "guid": self.calibration_widget.get_selected_guid()
            },
            "calibrations": self.gamepad_manager.get_calibrations()
        }

    def _on_active_toggle(self, active: bool) -> None:
        self.on_active_toggle(active)

        if active:
            self._on_calibration_start()
        else:
            self._on_calibration_done()

    def _on_control_key_change(self, control_name: str, key_code: int) -> None:
        controls = self.settings.get("controls", None)
        if controls:
            keyboard = controls.setdefault("keyboard", {})
            keyboard[control_name] = key_code

    def _on_calibration_start(self) -> None:
        self.on_active_toggle(True)
        for widget in self.key_widgets:
            widget.disable()

    def _on_calibration_done(self) -> None:
        self.on_active_toggle(False)
        for widget in self.key_widgets:
            widget.enable()

    def _draw_keyboard_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        y += self._draw_headline(surface, "keyboard", y)

        return self.keyboard_layout.draw(surface, y)

    def _draw_input_section(self, surface: Surface, y: int) -> int:
        y += self.y_section_padding
        y += self._draw_headline(surface, "input", y)

        return self.input_layout.draw(surface, y)
