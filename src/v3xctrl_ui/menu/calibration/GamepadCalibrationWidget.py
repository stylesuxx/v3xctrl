import pygame
from pygame import Surface
from pygame.freetype import Font
from typing import Callable, Dict, Optional

from v3xctrl_ui.colors import WHITE, GREY
from v3xctrl_ui.GamepadManager import GamepadManager

from v3xctrl_ui.menu.calibration.GamepadCalibrator import GamepadCalibrator, CalibratorState
from v3xctrl_ui.menu.DialogBox import DialogBox
from v3xctrl_ui.menu.input import Button, Checkbox, Select
from v3xctrl_ui.menu.input.BaseWidget import BaseWidget


class GamepadCalibrationWidget(BaseWidget):
    GAMEPAD_REFRESH_INTERVAL_MS = 1000
    BAR_WIDTH = 400
    BAR_HEIGHT = 30
    BAR_SPACING = 50
    INSTRUCTION_Y_OFFSET = 70
    BARS_X_OFFSSET = 100
    INVERT_X_OFFSET = 530

    def __init__(
        self,
        font: Font,
        manager: GamepadManager,
        on_calibration_start: Callable[[], None] = lambda: None,
        on_calibration_done: Callable[[], None] = lambda: None,
    ):
        super().__init__()
        self.font = font
        self.manager = manager
        self.on_calibration_start = on_calibration_start
        self.on_calibration_done = on_calibration_done

        self.selected_guid: Optional[str] = None
        self.calibrator: Optional[GamepadCalibrator] = None
        self.invert_axes: Dict[str, bool] = {k: False for k in ["steering", "throttle", "brake"]}

        self.controller_select: Select
        self.calibrate_button: Button
        self.invert_checkboxes: Dict[str, Checkbox]

        self.dialog = DialogBox(title="Next Step", lines=[], button_label="OK", on_confirm=lambda: None)

        self._create_ui(font)
        self.set_position(self.x, self.y)

        self.gamepads: Dict[str, pygame.joystick.Joystick] = self.manager.get_gamepads()
        self._on_gamepads_changed(self.gamepads)
        self.manager.add_observer(self._on_gamepads_changed)

    def _create_ui(self, font: Font):
        self.controller_select = Select(
            label="Controller",
            label_width=-10,
            width=400,
            font=font,
            callback=self.set_selected_gamepad
        )

        self.calibrate_button = Button(
            label="Start Calibration",
            width=190,
            height=35,
            font=font,
            callback=self._start_calibration
        )

        self.invert_checkboxes = {
            name: Checkbox(
                label="Invert",
                font=font,
                checked=False,
                on_change=lambda state, k=name: self.toggle_invert(k, state)
            ) for name in ["steering", "throttle", "brake"]
        }

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.dialog.visible:
            self.dialog.handle_event(event)
            return

        if self.gamepads:
            if self.controller_select.expanded:
                self.controller_select.handle_event(event)
                return
            else:
                self.calibrate_button.handle_event(event)
                self.controller_select.handle_event(event)
                for checkbox in self.invert_checkboxes.values():
                    checkbox.handle_event(event)

    def _on_gamepads_changed(self, gamepads: Dict[str, pygame.joystick.Joystick]):
        previous_guid = self.selected_guid
        self.gamepads = gamepads

        if previous_guid not in self.gamepads:
            self.selected_guid = next(iter(gamepads), None)
        else:
            self.selected_guid = previous_guid

        if not self.selected_guid:
            self.controller_select.set_options([], selected_index=0)
            self.calibrator = None
            return

        options = list(gamepads.items())
        guid_list = [guid for guid, _ in options]
        name_list = [js.get_name() for _, js in options]
        selected_index = guid_list.index(self.selected_guid)

        self.controller_select.set_options(name_list, selected_index=selected_index)
        self._apply_known_calibration(self.gamepads[self.selected_guid])

    def get_selected_guid(self):
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

    def _start_calibration(self) -> None:
        if self.calibrator and self.calibrator.state == CalibratorState.ACTIVE:
            return

        def on_done():
            self.calibrate_button.enable()
            self.controller_select.enable()

            js = self.gamepads.get(self.selected_guid)
            if js:
                guid = js.get_guid()
                settings = self.calibrator.get_settings()
                for setting in settings:
                    settings[setting]["invert"] = self.invert_axes.get(setting, False)

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

    def set_selected_gamepad(self, index: int) -> None:
        guids = list(self.gamepads.keys())
        if 0 <= index < len(guids):
            self.selected_guid = guids[index]
            self._apply_known_calibration(self.gamepads[self.selected_guid])

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

    def toggle_invert(self, key: str, state: bool) -> None:
        self.invert_axes[key] = state
        js = self.gamepads.get(self.selected_guid)
        if js:
            guid = js.get_guid()
            settings = self.manager.get_calibration(guid)
            if settings:
                settings[key]["invert"] = state
                self.manager.set_calibration(guid, settings)

    def draw(self, surface: Surface) -> None:
        if not self.gamepads:
            self._draw_no_gamepad_message(surface)
            return

        self._draw_ui_elements(surface)

        if not self.calibrator:
            return

        self._update_calibrator()

        if self.calibrator.state == CalibratorState.COMPLETE:
            self._draw_calibration_bars(surface)
        elif self.calibrator.stage is not None:
            self._draw_calibration_steps(surface)

        self.dialog.draw(surface)

    def _draw_no_gamepad_message(self, surface: Surface):
        text, rect = self.font.render("No gamepad detected. Please connect one...", WHITE)
        rect.topleft = (self.x, self.y + 20)
        surface.blit(text, rect)

    def _draw_ui_elements(self, surface: Surface):
        self.controller_select.draw(surface)
        self.calibrate_button.draw(surface)

    def _update_calibrator(self):
        js = self.gamepads.get(self.selected_guid)
        if js and js.get_init():
            axes = [js.get_axis(i) for i in range(js.get_numaxes())]
            self.calibrator.update(axes)

    def _draw_calibration_bars(self, surface: Surface):
        inputs = self.manager.read_inputs()
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

            self._draw_bar(
                surface, label, value,
                min_val, max_val, center_val,
                x=self.x + self.BARS_X_OFFSSET, y=y_base + i * self.BAR_SPACING
            )

            self.invert_checkboxes[key].set_position(self.x + self.INVERT_X_OFFSET, y_base + i * self.BAR_SPACING)
            self.invert_checkboxes[key].draw(surface)

    def _draw_calibration_steps(self, surface: Surface):
        y_base = self.y + self.INSTRUCTION_Y_OFFSET
        for i, (label, active) in enumerate(self.calibrator.get_steps()):
            color = WHITE if active else GREY
            rendered, rect = self.font.render(label, color)
            rect.topleft = (self.x, y_base + i * 40)
            surface.blit(rendered, rect)

    def _draw_bar(self, surface: Surface, label: str, value: float,
                  min_val: float, max_val: float,
                  center_val: float = None,
                  x: int = 0, y: int = 0,
                  width: int = BAR_WIDTH, height: int = BAR_HEIGHT) -> None:
        label_surf, label_rect = self.font.render(label, WHITE)
        label_rect.topleft = (x - 10 - label_rect.width, y + (height - label_rect.height) // 2)
        surface.blit(label_surf, label_rect)

        pygame.draw.rect(surface, GREY, (x, y, width, height), 1)
        fill_ratio = (value - min_val) / (max_val - min_val) if max_val != min_val else 0.5
        fill_px = int(max(0.0, min(1.0, fill_ratio)) * width)
        pygame.draw.rect(surface, WHITE, (x, y, fill_px, height))

        if center_val is not None:
            center_ratio = (center_val - min_val) / (max_val - min_val) if max_val != min_val else 0.5
            center_px = int(max(0.0, min(1.0, center_ratio)) * width)
            pygame.draw.line(surface, (200, 200, 0), (x + center_px, y), (x + center_px, y + height), 2)
