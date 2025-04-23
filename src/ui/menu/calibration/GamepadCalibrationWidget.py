import pygame
import threading
from pygame import Surface
from pygame.freetype import Font
from typing import List, Callable, Dict

from ui.menu.Button import Button
from ui.menu.Select import Select
from ui.colors import WHITE, GREY
from ui.menu.calibration.GamepadCalibrator import GamepadCalibrator, CalibratorState
from ui.menu.BaseWidget import BaseWidget


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
        self.gamepads: List[pygame.joystick.Joystick] = []
        self.selected_index: int = 0
        self.calibrator: GamepadCalibrator | None = None
        self._gamepads_dirty: bool = False

        self.calibrate_button = Button(
            label="Start Calibration",
            width=200,
            height=50,
            font=font,
            callback=self.start_calibration
        )

        self.controller_select = Select(
            label="Controller",
            label_width=150,
            width=400,
            font=font,
            callback=self.set_selected_gamepad
        )

        self.calibrate_button.set_position(self.x, self.y + 50)
        self.controller_select.set_position(self.x, self.y)

        pygame.joystick.init()
        self._refresh_gamepads()  # Ensure settings are applied immediately on startup
        self.thread = threading.Thread(target=self._background_gamepad_refresh, daemon=True)
        self.thread.start()

    def _refresh_gamepads(self):
        if not pygame.joystick.get_init():
            pygame.joystick.init()

        gamepads = []
        for i in range(pygame.joystick.get_count()):
            try:
                js = pygame.joystick.Joystick(i)
                if not js.get_init():
                    js.init()
                gamepads.append(js)
            except pygame.error:
                continue

        if len(gamepads) != len(self.gamepads) or any(a.get_instance_id() != b.get_instance_id() for a, b in zip(gamepads, self.gamepads)):
            self.gamepads = gamepads
            if self.selected_index >= len(self.gamepads):
                self.selected_index = 0
            self._gamepads_dirty = True
            if self.selected_index < len(self.gamepads):
                self._apply_known_calibration(self.gamepads[self.selected_index])

    def _background_gamepad_refresh(self):
        while True:
            self._refresh_gamepads()
            pygame.time.wait(self.GAMEPAD_REFRESH_INTERVAL_MS)

    def set_position(self, x: int, y: int) -> None:
        super().set_position(x, y)
        self.controller_select.set_position(x, y)
        self.calibrate_button.set_position(x, y + 50)

    def set_selected_gamepad(self, index: int) -> None:
        self.selected_index = index
        if self.selected_index < len(self.gamepads):
            self._apply_known_calibration(self.gamepads[self.selected_index])

    def _apply_known_calibration(self, js: pygame.joystick.Joystick) -> None:
        guid = js.get_guid()
        if guid in self.known_calibrations:
            settings = self.known_calibrations[guid]
            self.calibrator = GamepadCalibrator(lambda: None, lambda: None)
            self.calibrator.state = CalibratorState.COMPLETE
            self.calibrator._settings = settings
            self.calibrator.get_settings = lambda: settings

    def get_selected_index(self) -> int:
        return self.selected_index

    def start_calibration(self) -> None:
        if self.calibrator and self.calibrator.state == CalibratorState.ACTIVE:
            return

        def on_done():
            self.calibrate_button.enable()
            self.controller_select.enable()

            if self.selected_index < len(self.gamepads):
                js = self.gamepads[self.selected_index]
                guid = js.get_guid()
                settings = self.calibrator.get_settings()
                print("Calibration settings for", guid)
                print(settings)
                self.known_calibrations[guid] = settings
                self.on_calibration_done(guid, settings)

        self.calibrator = GamepadCalibrator(
            on_start=lambda: (
                self.calibrate_button.disable(),
                self.controller_select.disable()
            ),
            on_done=on_done
        )
        self.calibrator.start()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.gamepads:
            self.calibrate_button.handle_event(event)
            self.controller_select.handle_event(event)

    def draw(self, surface: Surface) -> None:
        if self._gamepads_dirty:
            self._gamepads_dirty = False
            self.controller_select.set_options(
                [g.get_name() for g in self.gamepads],
                selected_index=self.selected_index
            )

        if not self.gamepads:
            text, rect = self.font.render("No gamepad detected. Please connect one...", WHITE)
            rect.topleft = (self.x, self.y + 20)
            surface.blit(text, rect)
            return

        self.controller_select.draw(surface)
        self.calibrate_button.draw(surface)

        if not self.calibrator:
            return

        if self.selected_index < len(self.gamepads):
            js = self.gamepads[self.selected_index]
            if js.get_init():
                axes = [js.get_axis(i) for i in range(js.get_numaxes())]
                self.calibrator.update(axes)

        y_base = self.y + self.INSTRUCTION_Y_OFFSET

        if self.calibrator.state == CalibratorState.COMPLETE:
            settings = self.calibrator.get_settings()
            if self.selected_index < len(self.gamepads):
                js = self.gamepads[self.selected_index]

                def safe_get_axis(axis_idx):
                    try:
                        return js.get_axis(axis_idx)
                    except (AttributeError, IndexError, pygame.error):
                        return 0.0

                for i, (label, key) in enumerate([("Steering", "steering"),
                                                  ("Throttle", "throttle"),
                                                  ("Brake", "brake")]):
                    data = settings[key]
                    if data["axis"] is not None:
                        self._draw_bar(surface, label, safe_get_axis(data["axis"]),
                                       data["min"], data["max"], data.get("center"),
                                       x=self.x + 150, y=y_base + i * self.BAR_SPACING)

        elif self.calibrator.stage is not None:
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
        fill_px = int(fill_ratio * width)
        pygame.draw.rect(surface, WHITE, (x, y, fill_px, height))

        if center_val is not None:
            center_ratio = (center_val - min_val) / (max_val - min_val) if max_val != min_val else 0.5
            center_px = int(center_ratio * width)
            pygame.draw.line(surface, (200, 200, 0), (x + center_px, y), (x + center_px, y + height), 2)
