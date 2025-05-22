from pygame import Surface, event

from v3xctrl_ui.menu.tabs.Tab import Tab
from v3xctrl_ui.menu.KeyMappingWidget import KeyMappingWidget
from v3xctrl_ui.menu.calibration.GamepadCalibrationWidget import GamepadCalibrationWidget
from v3xctrl_ui.fonts import LABEL_FONT


class InputTab(Tab):
    def __init__(self, settings: dict, width: int, height: int, padding: int, y_offset: int, gamepad_manager, on_active_toggle):
        super().__init__(settings, width, height, padding, y_offset)

        self.on_active_toggle = on_active_toggle
        self.gamepad_manager = gamepad_manager

        self.key_widgets = []
        keyboard_controls = self.settings.get("controls", {}).get("keyboard", {})

        for name, key in keyboard_controls.items():
            widget = KeyMappingWidget(
                control_name=name,
                key_code=key,
                font=LABEL_FONT,
                on_key_change=lambda new_key, name=name: self._on_control_key_change(name, new_key),
                on_remap_toggle=self._on_active_toggle
            )
            self.key_widgets.append(widget)

        self.calibration_widget = GamepadCalibrationWidget(
            font=LABEL_FONT,
            manager=self.gamepad_manager,
            on_calibration_start=self._on_calibration_start,
            on_calibration_done=self._on_calibration_done
        )

    def _on_active_toggle(self, active: bool):
        self.on_active_toggle(active)

        if active:
            self._on_calibration_start()
        else:
            self._on_calibration_done()

    def _on_control_key_change(self, control_name, key_code):
        controls = self.settings.get("controls")
        keyboard = controls.setdefault("keyboard", {})
        keyboard[control_name] = key_code

    def _on_calibration_start(self):
        self.on_active_toggle(True)
        for widget in self.key_widgets:
            widget.disable()

    def _on_calibration_done(self):
        self.on_active_toggle(False)
        for widget in self.key_widgets:
            widget.enable()

    def handle_event(self, event: event.Event):
        for widget in self.key_widgets:
            widget.handle_event(event)
        self.calibration_widget.handle_event(event)

    def draw(self, surface: Surface):
        y = self.y_offset + self.padding
        y = self._draw_headline(surface, "Keyboard", y)

        y += 20
        for widget in self.key_widgets:
            widget.set_position(self.padding, y)
            widget.draw(surface)
            y += 40

        y += 20
        y = self._draw_headline(surface, "Input device", y)

        y += 20
        self.calibration_widget.set_position(self.padding, y)
        self.calibration_widget.draw(surface)

    def get_settings(self) -> dict:
        return {
            "input": {
                "guid": self.calibration_widget.get_selected_guid()
            },
            "calibrations": self.gamepad_manager.get_calibrations()
        }
