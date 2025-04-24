import pygame
from pygame import Surface
from pygame.freetype import Font
from typing import Callable, Dict, List

from ui.menu.BaseWidget import BaseWidget
from ui.menu.Button import Button
from ui.menu.Select import Select
from ui.menu.Checkbox import Checkbox
from ui.colors import WHITE, GREY
from ui.menu.calibration.GamepadCalibrator import GamepadCalibrator, CalibratorState
from ui.menu.calibration.GamepadManager import GamepadManager


class GamepadCalibrationWidget(BaseWidget):
    GAMEPAD_REFRESH_INTERVAL_MS = 1000
    BAR_WIDTH = 400
    BAR_HEIGHT = 30
    BAR_SPACING = 50
    INSTRUCTION_Y_OFFSET = 140

    def __init__(self, font: Font, on_calibration_done: Callable[[str, dict], None] = lambda guid, settings: None, known_calibrations: Dict[str, dict] = {}):
        super().__init__()
        self.font = font
        self.on_calibration_done = on_calibration_done
        self.known_calibrations = known_calibrations
        self.selected_index: int = 0
        self.calibrator: GamepadCalibrator | None = None
        self.invert_axes: Dict[str, bool] = {k: False for k in ["steering", "throttle", "brake"]}
        self.gamepads: List[pygame.joystick.Joystick] = []

        self.manager = GamepadManager()
        self.manager.add_observer(self._on_gamepads_changed)

        self.controller_select = Select(
            label="Controller",
            label_width=150,
            width=400,
            font=font,
            callback=self.set_selected_gamepad
        )

        self.calibrate_button = Button(
            label="Start Calibration",
            width=200,
            height=50,
            font=font,
            callback=self._start_calibration
        )

        self.invert_checkboxes: Dict[str, Checkbox] = {
            name: Checkbox(
                label="Invert",
                font=font,
                checked=False,
                on_change=lambda state, k=name: self.toggle_invert(k, state)
            ) for name in ["steering", "throttle", "brake"]
        }

        # Set initial positions (moved to set_position for proper layout refresh)
        self.set_position(self.x, self.y)

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.gamepads:
            if self.controller_select.expanded:
                self.controller_select.handle_event(event)
            else:
                self.calibrate_button.handle_event(event)
                self.controller_select.handle_event(event)
                for checkbox in self.invert_checkboxes.values():
                    checkbox.handle_event(event)

    def _on_gamepads_changed(self, gamepads: List[pygame.joystick.Joystick]):
        self.gamepads = gamepads

        if not self.gamepads:
            self.selected_index = 0
            self.controller_select.set_options([], selected_index=0)
            self.calibrator = None
            return

        self.selected_index = min(self.manager.get_selected_index(), len(self.gamepads) - 1)
        self.manager.set_selected_index(self.selected_index)

        self.controller_select.set_options(
            [g.get_name() for g in self.gamepads],
            selected_index=self.selected_index
        )

        if self.selected_index < len(self.gamepads):
            self._apply_known_calibration(self.gamepads[self.selected_index])

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)
        self.controller_select.set_position(x, y)
        self.calibrate_button.set_position(x, y + 60)

    def _start_calibration(self) -> None:
        if self.calibrator and self.calibrator.state == CalibratorState.ACTIVE:
            return

        def on_done():
            self.calibrate_button.enable()
            self.controller_select.enable()

            if self.selected_index < len(self.gamepads):
                js = self.gamepads[self.selected_index]
                guid = js.get_guid()
                settings = self.calibrator.get_settings()
                settings_with_inversion = settings.copy()
                for k in settings_with_inversion:
                    settings_with_inversion[k]["invert"] = self.invert_axes.get(k, False)

                self.known_calibrations[guid] = settings_with_inversion
                self.on_calibration_done(guid, settings_with_inversion)

        self.calibrator = GamepadCalibrator(
            on_start=lambda: (
                self.calibrate_button.disable(),
                self.controller_select.disable()
            ),
            on_done=on_done
        )
        self.calibrator.start()

    def set_selected_gamepad(self, index: int) -> None:
        self.selected_index = index
        self.manager.set_selected_index(index)
        if self.selected_index < len(self.gamepads):
            self._apply_known_calibration(self.gamepads[self.selected_index])

    def _apply_known_calibration(self, js: pygame.joystick.Joystick) -> None:
        guid = js.get_guid()
        if guid in self.known_calibrations:
            settings = self.known_calibrations[guid]
            for k in ["steering", "throttle", "brake"]:
                if "invert" not in settings.get(k, {}):
                    settings.setdefault(k, {})["invert"] = False
            self.calibrator = GamepadCalibrator(lambda: None, lambda: None)
            self.calibrator.state = CalibratorState.COMPLETE
            self.calibrator._settings = settings
            self.calibrator.get_settings = lambda: settings
            for k in self.invert_axes:
                self.invert_axes[k] = settings.get(k, {}).get("invert", False)
                self.invert_checkboxes[k].checked = self.invert_axes[k]

    def toggle_invert(self, key: str, state: bool) -> None:
        self.invert_axes[key] = state
        if self.selected_index < len(self.gamepads):
            js = self.gamepads[self.selected_index]
            guid = js.get_guid()
            if guid in self.known_calibrations:
                self.known_calibrations[guid][key]["invert"] = state
                self.on_calibration_done(guid, self.known_calibrations[guid])

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

    def _draw_no_gamepad_message(self, surface: Surface):
        text, rect = self.font.render("No gamepad detected. Please connect one...", WHITE)
        rect.topleft = (self.x, self.y + 20)
        surface.blit(text, rect)

    def _draw_ui_elements(self, surface: Surface):
        self.controller_select.draw(surface)
        self.calibrate_button.draw(surface)

    def _update_calibrator(self):
        if self.selected_index < len(self.gamepads):
            js = self.gamepads[self.selected_index]
            if js.get_init():
                axes = [js.get_axis(i) for i in range(js.get_numaxes())]
                self.calibrator.update(axes)

    def _draw_calibration_bars(self, surface: Surface):
        settings = self.calibrator.get_settings()
        if self.selected_index < len(self.gamepads):
            js = self.gamepads[self.selected_index]

            def safe_get_axis(axis_idx):
                try:
                    return js.get_axis(axis_idx)
                except (AttributeError, IndexError, pygame.error):
                    return 0.0

            y_base = self.y + self.INSTRUCTION_Y_OFFSET
            for i, (label, key) in enumerate([("Steering", "steering"),
                                              ("Throttle", "throttle"),
                                              ("Brake", "brake")]):
                data = settings[key]
                if data["axis"] is not None:
                    value = safe_get_axis(data["axis"])
                    min_val = data["min"]
                    max_val = data["max"]
                    center_val = data.get("center")
                    if self.invert_axes.get(key):
                        min_val, max_val = max_val, min_val
                    self._draw_bar(surface, label, value,
                                   min_val, max_val, center_val,
                                   x=self.x + 150, y=y_base + i * self.BAR_SPACING)
                    self.invert_checkboxes[key].set_position(self.x + 580, y_base + i * self.BAR_SPACING)
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
        fill_ratio = max(0.0, min(1.0, fill_ratio))
        fill_px = int(fill_ratio * width)
        pygame.draw.rect(surface, WHITE, (x, y, fill_px, height))

        if center_val is not None:
            center_ratio = (center_val - min_val) / (max_val - min_val) if max_val != min_val else 0.5
            center_ratio = max(0.0, min(1.0, center_ratio))
            center_px = int(center_ratio * width)
            pygame.draw.line(surface, (200, 200, 0), (x + center_px, y), (x + center_px, y + height), 2)
