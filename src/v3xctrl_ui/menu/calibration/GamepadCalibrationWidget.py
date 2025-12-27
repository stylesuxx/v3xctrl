import pygame
from pygame import Surface
from pygame.freetype import Font
from typing import Callable, Dict, Optional

from v3xctrl_ui.utils.colors import WHITE, GREY, TRANSPARENT_GREY
from v3xctrl_ui.utils.fonts import MONO_FONT
from v3xctrl_ui.controllers.input.GamepadController import GamepadController

from v3xctrl_ui.menu.calibration.GamepadCalibrator import (
  GamepadCalibrator,
  CalibratorState,
)
from v3xctrl_ui.menu.DialogBox import DialogBox
from v3xctrl_ui.menu.input import (
  BaseWidget,
  Button,
  Checkbox,
  NumberInput,
  Select,
)


class GamepadCalibrationWidget(BaseWidget):
    GAMEPAD_REFRESH_INTERVAL_MS = 1000
    BAR_WIDTH = 400
    BAR_HEIGHT = 30
    BAR_SPACING = 50
    INSTRUCTION_Y_OFFSET = 70
    BARS_X_OFFSSET = 100
    INVERT_X_OFFSET = 530
    DEADBAND_X_OFFSET = 630

    def __init__(
        self,
        font: Font,
        manager: GamepadController,
        on_calibration_start: Callable[[], None] = lambda: None,
        on_calibration_done: Callable[[], None] = lambda: None,
    ) -> None:
        super().__init__()

        self.font = font
        self.manager = manager
        self.on_calibration_start = on_calibration_start
        self.on_calibration_done = on_calibration_done

        self.selected_guid: Optional[str] = None
        self.calibrator: Optional[GamepadCalibrator] = None
        self.invert_axes: Dict[str, bool] = {k: False for k in ["steering", "throttle", "brake"]}
        self.deadband_values: Dict[str, int] = {k: 0 for k in ["steering", "throttle", "brake"]}

        self.controller_select: Select
        self.calibrate_button: Button
        self.invert_checkboxes: Dict[str, Checkbox]
        self.deadband_inputs: Dict[str, NumberInput]

        self.dialog = DialogBox(title="Next Step", lines=[], button_label="OK", on_confirm=lambda: None)

        self._create_ui(font)
        self.set_position(self.x, self.y)

        self.gamepads: Dict[str, pygame.joystick.Joystick] = self.manager.get_gamepads()
        self._on_gamepads_changed(self.gamepads)

        # When gamepads change, trigger handler
        self.manager.add_observer(self._on_gamepads_changed)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.dialog.visible:
            return self.dialog.handle_event(event)

        if self.gamepads:
            if self.controller_select.expanded:
                return self.controller_select.handle_event(event)
            else:
                handled = False
                handled |= self.calibrate_button.handle_event(event)
                handled |= self.controller_select.handle_event(event)

                for checkbox in self.invert_checkboxes.values():
                    handled |= checkbox.handle_event(event)

                for input_widget in self.deadband_inputs.values():
                    handled |= input_widget.handle_event(event)

                return handled

        return False

    def get_selected_guid(self) -> str | None:
        return self.selected_guid

    def get_size(self) -> tuple[int, int]:
        select_width, select_height = self.controller_select.get_size()
        button_width, button_height = self.calibrate_button.get_size()

        total_width = select_width + 10 + button_width
        max_height = max(select_height, button_height)

        return total_width, max_height

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)
        self.controller_select.set_position(x, y)

        select_width, select_height = self.controller_select.get_size()
        _, button_height = self.calibrate_button.get_size()
        button_y = y + select_height // 2 - button_height // 2

        self.calibrate_button.set_position(x + select_width + 20, button_y)

    def toggle_invert(self, key: str, state: bool) -> None:
        self.invert_axes[key] = state
        js = self.gamepads.get(self.selected_guid)
        if js:
            guid = str(js.get_guid())
            settings = self.manager.get_calibration(guid)
            settings[key]["invert"] = state
            self.manager.set_calibration(guid, settings)

    def update_deadband(self, key: str, value: str) -> None:
        try:
            deadband_val = int(value) if value else 0
            self.deadband_values[key] = deadband_val

            js = self.gamepads.get(self.selected_guid)
            if js:
                guid = str(js.get_guid())
                settings = self.manager.get_calibration(guid)
                if settings and key in settings:
                    settings[key]["deadband"] = deadband_val
                    self.manager.set_calibration(guid, settings)

        except ValueError:
            pass

    def set_selected_gamepad(self, index: int) -> None:
        guids = list(self.gamepads.keys())
        if 0 <= index < len(guids):
            self.selected_guid = guids[index]
            self._apply_known_calibration(self.gamepads[self.selected_guid])

    def _create_ui(self, font: Font) -> None:
        self.controller_select = Select(
            label="Controller",
            label_width=-10,
            length=400,
            font=font,
            callback=self.set_selected_gamepad
        )

        self.calibrate_button = Button(
            "Start Calibration",
            font,
            self._start_calibration
        )

        self.invert_checkboxes = {
            name: Checkbox(
                label="Invert",
                font=font,
                checked=False,
                on_change=lambda state, k=name: self.toggle_invert(k, state)
            ) for name in ["steering", "throttle", "brake"]
        }

        self.deadband_inputs = {
            name: NumberInput(
                label="Deadband %",
                label_width=85,
                input_width=50,
                min_val=0,
                max_val=100,
                font=font,
                mono_font=MONO_FONT,
                on_change=lambda value, k=name: self.update_deadband(k, value)
            ) for name in ["steering", "throttle", "brake"]
        }

    def _on_gamepads_changed(
        self,
        gamepads: Dict[str, pygame.joystick.Joystick]
    ) -> None:
        self.gamepads = gamepads

        if not self.selected_guid:
            # set to active one, if any
            self.selected_guid = self.manager.get_active()

        if self.selected_guid not in self.gamepads:
            # If gamepad no longer available, set the next one in the list as
            # selected
            self.selected_guid = next(iter(gamepads), None)

        if not self.selected_guid:
            # No gamepads available
            self.controller_select.set_options([], selected_index=0)
            self.calibrator = None
            return

        options = list(gamepads.items())
        guid_list = [guid for guid, _ in options]
        name_list = [js.get_name() for _, js in options]
        selected_index = guid_list.index(self.selected_guid)

        self.controller_select.set_options(name_list, selected_index=selected_index)
        self._apply_known_calibration(self.gamepads[self.selected_guid])

    def _start_calibration(self) -> None:
        if self.calibrator and self.calibrator.state == CalibratorState.ACTIVE:
            return

        def on_done() -> None:
            self.calibrate_button.enable()
            self.controller_select.enable()

            js = self.gamepads.get(self.selected_guid)
            if js:
                guid = js.get_guid()
                settings = self.calibrator.get_settings()
                for setting in settings:
                    settings[setting]["invert"] = self.invert_axes.get(setting, False)
                    settings[setting]["deadband"] = self.deadband_values.get(setting, 0)

                self.manager.set_calibration(guid, settings)
                self.manager.set_active(guid)
                self.on_calibration_done()

        self.calibrator = GamepadCalibrator(
            on_start=lambda: (
                self.calibrate_button.disable(),
                self.controller_select.disable(),
                self.on_calibration_start()
            ),
            on_done=on_done,
            dialog=self.dialog
        )
        self.calibrator.start()

    def _apply_known_calibration(self, js: pygame.joystick.Joystick) -> None:
        guid = js.get_guid()
        settings = self.manager.get_calibration(guid)
        if settings:
            self.manager.set_active(guid)
            self.calibrator = GamepadCalibrator(lambda: None, lambda: None)
            self.calibrator.state = CalibratorState.COMPLETE
            self.calibrator._settings = settings
            self.calibrator.get_settings = lambda: settings
            for k in self.invert_axes:
                self.invert_axes[k] = settings.get(k, {}).get("invert", False)
                self.invert_checkboxes[k].checked = self.invert_axes[k]

                self.deadband_values[k] = settings.get(k, {}).get("deadband", 0)
                self.deadband_inputs[k].value = str(self.deadband_values[k])

    def _draw(self, surface: Surface) -> None:
        if not self.gamepads:
            self._draw_no_gamepad_message(surface)
            return

        if self.calibrator:
            self._update_calibrator()

            if self.calibrator.state == CalibratorState.COMPLETE:
                self._draw_calibration_bars(surface)
            elif self.calibrator.stage is not None:
                self._draw_calibration_steps(surface)

        # Draw UI elements before dialog so Select options can overlap bars but not dialog
        self._draw_ui_elements(surface)

        # Draw dialog last so it appears on top of everything
        if self.calibrator:
            self.dialog.draw(surface)

    def _draw_no_gamepad_message(self, surface: Surface) -> None:
        text, rect = self.font.render("No gamepad detected. Please connect one...", WHITE)
        rect.topleft = (self.x, self.y + 20)
        surface.blit(text, rect)

    def _draw_ui_elements(self, surface: Surface) -> None:
        self.controller_select.draw(surface)
        self.calibrate_button.draw(surface)

    def _update_calibrator(self) -> None:
        js = self.gamepads.get(self.selected_guid)
        if js and js.get_init():
            axes = [js.get_axis(i) for i in range(js.get_numaxes())]
            self.calibrator.update(axes)

    def _draw_calibration_bars(self, surface: Surface) -> None:
        # Get raw inputs (without deadband) for display
        inputs = self.manager.read_inputs(apply_deadband=False)
        if not inputs:
            return

        settings = self.manager.get_calibration(self.selected_guid)
        if not settings:
            return

        y_base = self.y + self.INSTRUCTION_Y_OFFSET
        for i, (label, key) in enumerate([("Steering", "steering"),
                                          ("Throttle", "throttle"),
                                          ("Brake", "brake")]):
            value = inputs.get(key, 0.0)
            config = settings.get(key, {})

            center = config.get("center")
            center_val = None
            min_val = 0.0
            max_val = 1.0
            if center is not None:
                center_val = 0.0
                min_val = -1.0

            deadband_pct = config.get("deadband", 0) / 100.0

            self._draw_bar(
                surface, label, value,
                min_val, max_val, center_val,
                deadband_pct=deadband_pct,
                x=self.x + self.BARS_X_OFFSSET, y=y_base + i * self.BAR_SPACING
            )

            # Calculate y position for the row - align to bar center
            row_y = y_base + i * self.BAR_SPACING
            bar_center_y = row_y + self.BAR_HEIGHT // 2

            # Position checkbox - center it vertically with the bar
            checkbox_height = self.invert_checkboxes[key].get_size()[1]
            checkbox_y = bar_center_y - checkbox_height // 2
            self.invert_checkboxes[key].set_position(self.x + self.INVERT_X_OFFSET, checkbox_y)
            self.invert_checkboxes[key].draw(surface)

            # Position number input - center it vertically with the bar
            input_height = self.deadband_inputs[key].get_size()[1]
            input_y = bar_center_y - input_height // 2
            self.deadband_inputs[key].set_position(self.x + self.DEADBAND_X_OFFSET, input_y)
            self.deadband_inputs[key].draw(surface)

    def _draw_calibration_steps(self, surface: Surface) -> None:
        y_base = self.y + self.INSTRUCTION_Y_OFFSET
        for i, (label, active) in enumerate(self.calibrator.get_steps()):
            color = WHITE if active else GREY
            rendered, rect = self.font.render(label, color)
            rect.topleft = (self.x, y_base + i * 40)
            surface.blit(rendered, rect)

    def _draw_bar(
        self,
        surface: Surface,
        label: str,
        value: float,
        min_val: float,
        max_val: float,
        center_val: Optional[float] = None,
        deadband_pct: float = 0.0,
        x: int = 0,
        y: int = 0,
        width: int = BAR_WIDTH,
        height: int = BAR_HEIGHT
    ) -> None:
        label_surf, label_rect = self.font.render(label, WHITE)
        label_rect.topleft = (x - 10 - label_rect.width, y + (height - label_rect.height) // 2)
        surface.blit(label_surf, label_rect)

        pygame.draw.rect(surface, GREY, (x, y, width, height), 1)
        fill_ratio = (value - min_val) / (max_val - min_val) if max_val != min_val else 0.5
        fill_px = int(max(0.0, min(1.0, fill_ratio)) * width)
        pygame.draw.rect(surface, WHITE, (x, y, fill_px, height))

        # Draw deadband shaded region
        if deadband_pct > 0:
            if center_val is not None:
                # Centered axis: deadband around center
                # deadband_pct is the total percentage, so we use half on each side
                center_ratio = (center_val - min_val) / (max_val - min_val)
                center_px = int(center_ratio * width)
                deadband_px = int((deadband_pct / 2.0) * width)

                deadband_start = max(0, center_px - deadband_px)
                deadband_end = min(width, center_px + deadband_px)
                deadband_width = deadband_end - deadband_start

                # Create surface with alpha for shading
                deadband_surf = Surface((deadband_width, height), pygame.SRCALPHA)
                deadband_surf.fill(TRANSPARENT_GREY)
                surface.blit(deadband_surf, (x + deadband_start, y))
            else:
                # Non-centered axis: deadband from start
                deadband_px = int(deadband_pct * width)

                # Create surface with alpha for shading
                deadband_surf = Surface((deadband_px, height), pygame.SRCALPHA)
                deadband_surf.fill(TRANSPARENT_GREY)
                surface.blit(deadband_surf, (x, y))

        if center_val is not None:
            center_ratio = (center_val - min_val) / (max_val - min_val) if max_val != min_val else 0.5
            center_px = int(max(0.0, min(1.0, center_ratio)) * width)
            pygame.draw.line(surface, (200, 200, 0), (x + center_px, y), (x + center_px, y + height), 2)
