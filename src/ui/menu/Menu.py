import pygame
from pygame import Surface
from typing import Callable

from ui.GamepadManager import GamepadManager
from ui.Settings import Settings

from ui.menu.calibration.GamepadCalibrationWidget import GamepadCalibrationWidget
from ui.menu.NumberInput import NumberInput
from ui.menu.Checkbox import Checkbox
from ui.menu.Button import Button
from ui.menu.KeyMappingWidget import KeyMappingWidget

from ui.colors import WHITE, GREY, MID_GREY, DARK_GREY
from ui.fonts import MAIN_FONT, LABEL_FONT, TEXT_FONT, MONO_FONT


class Menu:
    BG_COLOR = DARK_GREY
    TAB_ACTIVE_COLOR = MID_GREY
    TAB_INACTIVE_COLOR = GREY
    TAB_SEPARATOR_COLOR = BG_COLOR
    FONT_COLOR = WHITE
    LINE_COLOR = WHITE

    def __init__(self,
                 width: int,
                 height: int,
                 gamepad_manager: GamepadManager,
                 settings: Settings,
                 callback: Callable[[], None]):
        self.width = width
        self.height = height
        self.gamepad_manager = gamepad_manager
        self.settings = settings
        self.callback = callback

        self.tabs = ["General", "Video", "Input"]
        self.active_tab = self.tabs[0]
        self.disable_tabs = False

        self.tab_height = 60
        self.footer_height = 60
        self.padding = 20

        self.tab_rects = self._generate_tab_rects()

        button_y = self.height - self.footer_height
        self.save_button = Button(
            "Save",
            100, 40,
            MAIN_FONT,
            self._save_button_callback)
        self.save_button.set_position(self.width - 240, button_y)

        self.exit_button = Button(
            "Back",
            100, 40,
            MAIN_FONT,
            self._exit_button_callback)
        self.exit_button.set_position(self.width - 120, button_y)

        # General widgets
        self.debug = self.settings.get("debug", False)
        self.ports = self.settings.get("ports", {})

        self.video_input = NumberInput(
            "Video",
            label_width=90,
            input_width=75,
            min_val=1,
            max_val=65535,
            font=LABEL_FONT,
            mono_font=MONO_FONT,
            on_change=lambda v: self._on_port_change("video", v)
        )
        self.video_input.set_position(self.padding, self.tab_height + self.padding + 60)

        self.control_input = NumberInput(
            "Control",
            label_width=90,
            input_width=75,
            min_val=1,
            max_val=65535,
            font=LABEL_FONT,
            mono_font=MONO_FONT,
            on_change=lambda v: self._on_port_change("control", v)
        )
        self.control_input.set_position(self.padding, self.tab_height + self.padding + 100)

        # Miscellaneous widgets
        self.debug_checkbox = Checkbox(
            label="Enable Debug Overlay",
            font=LABEL_FONT,
            checked=self.settings.get("debug", False),
            on_change=lambda v: self._on_debug_change(v)
        )

        # Input widgets
        keyboard_controls = self.settings.get("controls", {}).get("keyboard", {})
        self.key_widgets = []

        for name, key in keyboard_controls.items():
            widget = KeyMappingWidget(
                control_name=name,
                key_code=key,
                font=LABEL_FONT,
                on_key_change=lambda new_key, name=name: self._on_control_key_change(name, new_key),
                on_remap_toggle=self._on_remap_toggle
            )
            self.key_widgets.append(widget)

        self.calibration_widget = GamepadCalibrationWidget(
            font=LABEL_FONT,
            manager=gamepad_manager,
            on_calibration_start=self._on_calibration_start,
            on_calibration_done=self._on_calibration_done
        )

        self.video_input.value = str(self.ports["video"])
        self.video_input.cursor_pos = len(self.video_input.value)

        self.control_input.value = str(self.ports["control"])
        self.control_input.cursor_pos = len(self.control_input.value)

        self.background = pygame.Surface((self.width, self.height))
        self.background.fill(self.BG_COLOR)

    def _on_remap_toggle(self, is_remapping: bool):
        if is_remapping:
            self.disable_tabs = True
            self.save_button.disable()
            self.exit_button.disable()
            for widget in self.key_widgets:
                widget.disable()
        else:
            self.disable_tabs = False
            self.save_button.enable()
            self.exit_button.enable()
            for widget in self.key_widgets:
                widget.enable()

    def _on_calibration_start(self):
        self.disable_tabs = True
        self.save_button.disable()
        self.exit_button.disable()
        for widget in self.key_widgets:
            widget.disable()

    def _on_calibration_done(self, guid: str, settings: dict):
        self.disable_tabs = False
        self.save_button.enable()
        self.exit_button.enable()
        for widget in self.key_widgets:
            widget.enable()

    def _on_port_change(self, name: str, value: str):
        self.ports[name] = int(value)

    def _on_debug_change(self, value: str):
        self.debug = value

    def _save_button_callback(self):
        if self.active_tab == "General":
            self.settings.set("ports", self.ports)
            self.settings.set("debug", self.debug)

        elif self.active_tab == "Input":
            guid = self.calibration_widget.get_selected_guid()
            self.settings.set("input", {"guid": guid})

            calibrations = self.gamepad_manager.get_calibrations()
            self.settings.set("calibrations", calibrations)

        self.settings.save()

    def _exit_button_callback(self):
        self.active_tab = self.tabs[0]
        self.callback()

    def _on_control_key_change(self, control_name, key_code):
        controls = self.settings.get("controls")
        keyboard = controls.setdefault("keyboard", {})
        keyboard[control_name] = key_code

    def _generate_tab_rects(self):
        tab_width = self.width // len(self.tabs)
        return {
            name: pygame.Rect(i * tab_width, 0, tab_width, self.tab_height)
            for i, name in enumerate(self.tabs)
        }

    def handle_event(self, event):
        self.save_button.handle_event(event)
        self.exit_button.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.disable_tabs:
                for tab, rect in self.tab_rects.items():
                    if rect.collidepoint(event.pos):
                        self.active_tab = tab

        if self.active_tab == "General":
            self.video_input.handle_event(event)
            self.control_input.handle_event(event)
            self.debug_checkbox.handle_event(event)

        elif self.active_tab == "Input":
            for widget in self.key_widgets:
                widget.handle_event(event)

            self.calibration_widget.handle_event(event)

    def _draw_headline(self, surface: Surface, title: str, y: int) -> int:
        heading_surface, _ = MAIN_FONT.render(title, self.FONT_COLOR)
        heading_pos = (self.padding, y)
        surface.blit(heading_surface, heading_pos)
        pygame.draw.line(surface, self.LINE_COLOR,
                         (self.padding, y + 40),
                         (self.width - self.padding, y + 40), 2)

        return y + 40

    def draw(self, surface: Surface):
        surface.blit(self.background, (0, 0))

        for i, (tab, rect) in enumerate(self.tab_rects.items()):
            color = self.TAB_ACTIVE_COLOR if tab == self.active_tab else self.TAB_INACTIVE_COLOR
            pygame.draw.rect(surface, color, rect)
            if i > 0:
                pygame.draw.line(surface, self.TAB_SEPARATOR_COLOR, rect.topleft, rect.bottomleft, 2)
            label_surface, label_rect = MAIN_FONT.render(tab, self.FONT_COLOR)
            label_rect.center = rect.center
            surface.blit(label_surface, label_rect)

        self.save_button.draw(surface)
        self.exit_button.draw(surface)

        if self.active_tab == "Input":
            ports_section_y = self.tab_height + self.padding
            baseline = self._draw_headline(surface, "Keyboard", ports_section_y)

            # Draw each key remapping row
            row_y = baseline + 20
            for widget in self.key_widgets:
                widget.set_position(self.padding, row_y)

                widget.draw(surface)
                row_y += 40

            row_y += 20
            baseline = self._draw_headline(surface, "Input device", row_y)
            row_y = baseline + 20
            self.calibration_widget.set_position(self.padding, row_y)
            self.calibration_widget.draw(surface)

        if self.active_tab == "General":
            ports_section_y = self.tab_height + self.padding
            self._draw_headline(surface, "Ports", ports_section_y)

            self.video_input.draw(surface)
            self.control_input.draw(surface)

            # Note about restarting
            note_text = "Remember to restart the app after changing the ports!"
            note_surface, note_rect = TEXT_FONT.render(note_text, self.FONT_COLOR)
            note_rect.topleft = (
                self.padding,
                self.control_input.y + self.control_input.input_height + 20
            )

            # --- Miscellaneous section ---
            misc_section_y = note_rect.bottom + self.padding + 10
            baseline = self._draw_headline(surface, "Miscellaneous", misc_section_y)

            # Set checkbox y dynamically
            y = baseline + 20
            self.debug_checkbox.set_position(self.padding, y)
            self.debug_checkbox.draw(surface)

            surface.blit(note_surface, note_rect)
