from typing import Callable, Dict, List, Any

from pygame import Surface

from v3xctrl_ui.utils.fonts import LABEL_FONT
from v3xctrl_ui.utils.i18n import t
from v3xctrl_ui.core.controllers.input.GamepadController import GamepadController
from v3xctrl_ui.menu.calibration.GamepadCalibrationWidget import (
  GamepadCalibrationWidget
)
from v3xctrl_ui.menu.input import KeyMappingWidget
from v3xctrl_ui.core.Settings import Settings

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
        gamepad_manager: GamepadController,
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
            on_calibration_done=self._on_calibration_done,
            on_remap_toggle=self._on_active_toggle
        )

        self.elements = self.key_widgets + [self.calibration_widget]

        # Column layout configuration
        self.column_spacing = 20
        self.keyboard_columns: List[VerticalLayout] = []

        self._add_headline("keyboard", t("Keyboard"))
        self._add_headline("input", t("Input device"), True)
        self._rebuild_columns()

        self.input_layout = VerticalLayout()
        self.input_layout.add(self.calibration_widget)

        self.apply_settings()

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

    def apply_settings(self) -> None:
        keyboard_controls = self.settings.get("controls", {}).get("keyboard", {})

        for widget in self.key_widgets:
            if widget.control_name in keyboard_controls:
                widget.key_code = keyboard_controls[widget.control_name]

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

    def _regenerate(self) -> None:
        """Override to also rebuild columns when dimensions change"""
        super()._regenerate()
        self._rebuild_columns()

    def _rebuild_columns(self) -> None:
        """Rebuild column layout based on current width"""
        num_columns = 3
        items_per_column = 4
        self.keyboard_columns = []

        if len(self.key_widgets) > 0:
            available_width = self.width - ((num_columns - 1) * self.padding)
            column_width = (available_width - (num_columns - 1) * self.column_spacing) // num_columns

            for i in range(num_columns):
                start = i * items_per_column
                end_idx = min(start + items_per_column, len(self.key_widgets))

                if start >= len(self.key_widgets):
                    break

                padding_x = self.padding + i * (column_width + self.column_spacing)

                column = VerticalLayout(padding_x=padding_x)
                for widget in self.key_widgets[start:end_idx]:
                    widget.set_column_width(column_width)
                    column.add(widget)

                self.keyboard_columns.append(column)

    def _draw_keyboard_section(self, surface: Surface, y: int) -> int:
        y += self.y_offset + self.padding
        y += self._draw_headline(surface, "keyboard", y)

        start_y = y
        for i, column in enumerate(self.keyboard_columns):
            column_y = column.draw(surface, start_y)

            # First column always has the most items, so use its y position
            if i == 0:
                y = column_y

        return y

    def _draw_input_section(self, surface: Surface, y: int) -> int:
        y += self.y_section_padding
        y += self._draw_headline(surface, "input", y)

        return self.input_layout.draw(surface, y)
